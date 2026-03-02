from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseBadRequest, HttpResponse
from django.conf import settings
import uuid
import json
import razorpay
from .models import Movie, Theater, Seat, Booking, Payment, Genre, Language
from .tasks import send_booking_confirmation_email
import threading

def movie_list(request):
    search_query = request.GET.get('search', '')
    selected_genres = request.GET.getlist('genres')
    selected_languages = request.GET.getlist('languages')
    sort_by = request.GET.get('sort', '-created_at')

    # Base queryset
    movies = Movie.objects.all().prefetch_related('genres', 'languages')

    # Apply search filter
    if search_query:
        movies = movies.filter(name__icontains=search_query)

    # 1. Result Set (Full filters applied)
    result_movies = movies
    if selected_genres:
        result_movies = result_movies.filter(genres__id__in=selected_genres).distinct()
    if selected_languages:
        result_movies = result_movies.filter(languages__id__in=selected_languages).distinct()

    # Apply sorting
    if sort_by in ['rating', '-rating', 'name', '-name', 'created_at', '-created_at']:
        result_movies = result_movies.order_by(sort_by)

    # Pagination
    paginator = Paginator(result_movies, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 2. Dynamic Counts (Faceted Search)
    # We use subqueries for filtering to avoid large IN clauses and multiple queries
    
    # Genre counts (filtered by Search + Languages)
    genre_filter_movies = movies
    if selected_languages:
        genre_filter_movies = genre_filter_movies.filter(languages__id__in=selected_languages).distinct()
    
    genre_counts = Genre.objects.annotate(
        movie_count=Count('movies', filter=Q(movies__id__in=genre_filter_movies.values('id')))
    ).filter(movie_count__gt=0).order_by('-movie_count')

    # Language counts (filtered by Search + Genres)
    lang_filter_movies = movies
    if selected_genres:
        lang_filter_movies = lang_filter_movies.filter(genres__id__in=selected_genres).distinct()
    
    lang_counts = Language.objects.annotate(
        movie_count=Count('movies', filter=Q(movies__id__in=lang_filter_movies.values('id')))
    ).filter(movie_count__gt=0).order_by('-movie_count')

    context = {
        'movies': page_obj,
        'genre_counts': genre_counts,
        'lang_counts': lang_counts,
        'selected_genres': [int(g) for g in selected_genres if g.isdigit()],
        'selected_languages': [int(l) for l in selected_languages if l.isdigit()],
        'sort_by': sort_by,
        'search_query': search_query,
    }
    return render(request, 'movies/movie_list.html', context)

def theater_list(request,movie_id):
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})



@login_required(login_url='/login/')
def book_seats(request, theater_id):
    theaters = get_object_or_404(Theater, id=theater_id)
    seats = Seat.objects.filter(theater=theaters)
    
    if request.method == 'POST':
        selected_Seats = request.POST.getlist('seats')
        error_seats = []
        booked_seat_numbers = []
        
        if not selected_Seats:
            return render(request, "movies/seat_selection.html", {'theater': theaters, "seats": seats, 'error': "No seat selected"})
            
        # Amount calculation (150 rupees per seat)
        seat_price = 150
        total_amount = len(selected_Seats) * seat_price
        total_amount_in_paise = total_amount * 100
        
        # Initialize Razorpay Client
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # Create Razorpay Order
        payment_data = {
            "amount": total_amount_in_paise,
            "currency": "INR",
            "payment_capture": "1" # 1 means Auto capture
        }
        
        try:
            razorpay_order = client.order.create(data=payment_data)
        except Exception as e:
            import traceback
            print(f"RAZORPAY ERROR: {str(e)}")
            traceback.print_exc()
            
            # Mask the key for security, but show enough to debug if Vercel loaded it
            key_id = getattr(settings, 'RAZORPAY_KEY_ID', 'None')
            masked_key = key_id[:12] + '...' if key_id else 'None'
            
            return render(request, "movies/seat_selection.html", {
                'theater': theaters, 
                "seats": seats, 
                'error': f"Authentication failed! Vercel is using key: '{masked_key}'. Ensure your Vercel Environment Variables are set AND you Redeployed!"
            })
        
        pending_bookings = []
        
        from django.db import transaction
        from django.utils import timezone
        
        try:
            with transaction.atomic():
                # Lock the requested seats. Blocks simultaneous database queries to these exact rows.
                # Ensure selected_Seats contains valid IDs to prevent issues with `id__in`
                valid_selected_seat_ids = [int(s_id) for s_id in selected_Seats if s_id.isdigit()]
                locked_seats = Seat.objects.select_for_update().filter(id__in=valid_selected_seat_ids, theater=theaters)
                
                # Check if all selected seats were found and locked
                if len(locked_seats) != len(valid_selected_seat_ids):
                    # This means some selected seat IDs were invalid or didn't belong to the theater
                    # Or, more critically, some seats might have been deleted between form submission and locking.
                    # For simplicity, we'll treat this as an error.
                    raise ValueError("One or more selected seats are invalid or unavailable.")

                # Check for conflicts AFTER securing the row-level lock
                for seat in locked_seats:
                    if seat.is_booked:
                        error_seats.append(seat.seat_number)
                        
                if error_seats:
                    raise ValueError("Seats already booked")
                
                for seat in locked_seats:
                    booking = Booking.objects.create(
                        user=request.user,
                        seat=seat,
                        movie=theaters.movie,
                        theater=theaters,
                        status='PENDING',
                        locked_at=timezone.now()
                    )
                    seat.is_booked = True
                    seat.save()
                    
                    booked_seat_numbers.append(seat.seat_number)
                    pending_bookings.append(booking)
                    
        except ValueError as e: # Catches "Seats already booked" or "invalid seats"
            return render(request, "movies/seat_selection.html", {
                'theater': theaters, 
                "seats": seats, 
                'error': f"Race condition prevented! {e}" if "Seats already booked" in str(e) else str(e)
            })
        except Exception as e: # Catches any other unexpected errors during the atomic block
            print(f"Error during atomic booking: {e}") # Log the error for debugging
            return render(request, "movies/seat_selection.html", {'theater': theaters, "seats": seats, 'error': "An unexpected error occurred while processing your booking. Please try again."})
            
        if pending_bookings:
            # Create the master Payment intent record
            Payment.objects.create(
                user=request.user,
                razorpay_order_id=razorpay_order['id'],
                amount=total_amount,
                status='CREATED'
            )
            
            context = {
                'theater': theaters, 
                'seats': seats,
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_amount': total_amount_in_paise,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'booked_seat_numbers': ', '.join(booked_seat_numbers),
                'total_amount': total_amount
            }
            # Redirect to the actual payment confirmation template
            return render(request, 'movies/checkout.html', context)
            
    return render(request, 'movies/seat_selection.html', {'theater': theaters, "seats": seats})

@csrf_exempt
@login_required(login_url='/login/')
def razorpay_callback(request):
    """
    Frontend callback simply displays Success or Failure to the user.
    Actual payment verification happens server-side via Webhooks.
    """
    if request.method == "POST":
        razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        razorpay_signature = request.POST.get('razorpay_signature', '')
        
        # Basic context for the UI
        context = {
            'order_id': razorpay_order_id,
            'payment_id': razorpay_payment_id
        }
        
        return render(request, 'movies/payment_success.html', context)
    return redirect('profile')

@csrf_exempt
def razorpay_webhook(request):
    """
    Secure server-side Webhook for listening to Razorpay events.
    Handles Idempotency to prevent redundant processing.
    """
    if request.method == "POST":
        print("WEBHOOK ACCESSED: Received POST request from Razorpay")
        webhook_body = request.body.decode('utf-8')
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        try:
            # 1. VERIFY SIGNATURE (Fraud Prevention!)
            client.utility.verify_webhook_signature(
                webhook_body, 
                webhook_signature, 
                settings.RAZORPAY_WEBHOOK_SECRET
            )
        except razorpay.errors.SignatureVerificationError:
            # Reject spoofed hooks
            return HttpResponseBadRequest("Invalid Signature")

        event = json.loads(webhook_body)
        event_type = event.get('event')
        
        # 2. Extract Data
        payload_order = event['payload'].get('order', {}).get('entity', {})
        payload_payment = event['payload'].get('payment', {}).get('entity', {})
        
        razorpay_order_id = payload_order.get('id') or payload_payment.get('order_id')
        if not razorpay_order_id:
            return HttpResponse("No Order ID in payload", status=200)
            
        try:
            payment = Payment.objects.get(razorpay_order_id=razorpay_order_id)
        except Payment.DoesNotExist:
            print(f"WEBHOOK ERROR: Payment for order {razorpay_order_id} not found in database.")
            return HttpResponse("Payment unknown", status=200)

        # 3. IDEMPOTENCY CHECK (Replay Attack Mitigation)
        if payment.status in ['CAPTURED', 'FAILED'] and event_type in ['order.paid', 'payment.failed']:
            print(f"WEBHOOK IGNORED: Payment {razorpay_order_id} already processed.")
            # We already processed this outcome. Ignore duplicate webhooks!
            return HttpResponse("Already processed", status=200)

        # 4. LIFECYCLE MANAGEMENT
        bookings = Booking.objects.filter(
            user=payment.user, 
            status='PENDING'
        ).order_by('booked_at')

        if event_type == 'order.paid':
            # Handle Success
            payment.status = 'CAPTURED'
            payment.razorpay_payment_id = payload_payment.get('id')
            
            # Specifically update the local amount to reflect the exact Razorpay successful deduction amount
            # Razorpay sends the amount in paise, so we divide by 100 to cast it back to standard Rupees.
            actual_deducted_paise = payload_payment.get('amount')
            if actual_deducted_paise:
                payment.amount = float(actual_deducted_paise) / 100.0
                
            payment.save()
            
            booked_seat_numbers = []
            theater = None
            movie_name = None
            
            for b in bookings:
                b.status = 'CONFIRMED'
                b.save()
                booked_seat_numbers.append(b.seat.seat_number)
                if not theater:
                    theater = b.theater
                    movie_name = b.movie.name
            
            # Send Email Asynchronously via Celery
            if booked_seat_numbers and payment.user.email and theater:
                booking_data = {
                    'user_name': payment.user.username,
                    'movie_name': movie_name,
                    'theater_name': theater.name,
                    'time': theater.time.strftime('%Y-%m-%d %H:%M'),
                    'seats': ', '.join(booked_seat_numbers),
                    'payment_id': payment.razorpay_payment_id
                }
                print(f"WEBHOOK SUCCESS: Payment {payment.razorpay_payment_id} captured. Starting email thread for {payment.user.email}...")
                email_thread = threading.Thread(
                    target=send_booking_confirmation_email, 
                    args=(payment.user.email, booking_data)
                )
                email_thread.start()

        elif event_type == 'payment.failed':
            # Handle Timeout/Failure
            payment.status = 'FAILED'
            payment.save()
            
            # FREE THE ABORTED SEATS!
            for b in bookings:
                b.status = 'FAILED'
                b.save()
                b.seat.is_booked = False
                b.seat.save()

        return HttpResponse("OK", status=200)
    return HttpResponseBadRequest()

@login_required(login_url='/login/')
def razorpay_cancel(request, order_id):
    """
    Called when a user manually closes the Razorpay checkout overlay.
    Frees the seats immediately so others can book them.
    """
    try:
        payment = Payment.objects.get(razorpay_order_id=order_id, user=request.user)
    except Payment.DoesNotExist:
        return redirect('movie_list')
        
    if payment.status == 'CREATED':
        payment.status = 'CANCELLED'
        payment.save()
        
        # Free pending seats
        bookings = Booking.objects.filter(user=request.user, status='PENDING')
        for b in bookings:
            # We must specifically free seats related to this session (where the payment links)
            # Since Payment has a 1-to-many implicit with Booking, we free PENDING ones
            b.status = 'CANCELLED'
            b.save()
            b.seat.is_booked = False
            b.seat.save()
            
    # Redirect back to the movie they were trying to book
    movie_id = request.GET.get('movie_id')
    if movie_id:
        return redirect('theater_list', movie_id)
    return redirect('movie_list')

 
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db.models import Count, Sum, Q
from movies.models import Movie, Theater, Booking, Payment
from datetime import timedelta, datetime

@staff_member_required(login_url='/login/')
def admin_dashboard(request):
    """
    Optimized admin analytics dashboard with Redis caching.
    Stats are cached for 5 minutes to avoid heavy DB queries on each request.
    """

    # Try fetching cached stats first
    stats = cache.get('admin_dashboard_stats')
    if stats:
        return render(request, 'movies/admin_dashboard.html', {'stats': stats})

    # -------------------
    # Heavy computation only if cache miss
    # -------------------

    # 1️⃣ Total revenue
    total_revenue = Payment.objects.filter(status='CAPTURED').aggregate(
        total=Sum('amount')
    )['total'] or 0

    # 2️⃣ Total bookings and cancellation rate
    total_bookings_count = Booking.objects.count()
    cancelled_count = Booking.objects.filter(status='CANCELLED').count()
    cancellation_rate = round((cancelled_count / total_bookings_count) * 100, 2) if total_bookings_count else 0

    # 3️⃣ Most popular movies (top 5)
    popular_movies = (
        Movie.objects.annotate(
            booking_count=Count('bookings', filter=Q(bookings__status__in=['PENDING', 'CONFIRMED']))
        )
        .values('id', 'name', 'booking_count')
        .order_by('-booking_count')[:5]
    )

    # 4️⃣ Busiest theaters (occupancy rate)
    theaters = Theater.objects.all().prefetch_related('seats', 'bookings')
    busiest_theaters = []
    for theater in theaters:
        total_seats = theater.seats.count()
        booked_seats = theater.seats.filter(is_booked=True).count()
        occupancy = (booked_seats / total_seats * 100) if total_seats else 0
        busiest_theaters.append({
            'id': theater.id,
            'name': theater.name,
            'occupancy': round(occupancy, 1)
        })
    # Sort by occupancy descending and pick top 5
    busiest_theaters = sorted(busiest_theaters, key=lambda x: x['occupancy'], reverse=True)[:5]

    # 5️⃣ Daily revenue (last 7 days)
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    daily_revenue = (
        Payment.objects.filter(status='CAPTURED', created_at__date__gte=week_ago)
        .extra({'day': "date(created_at)"})
        .values('day')
        .annotate(total=Sum('amount'))
        .order_by('day')
    )

    # 6️⃣ Peak booking hours (last 7 days)
    peak_hours_qs = (
        Booking.objects.filter(booked_at__date__gte=week_ago)
        .extra({'hour': "EXTRACT(hour FROM booked_at)"})
        .values('hour')
        .annotate(volume=Count('id'))
        .order_by('-volume')
    )
    peak_hours = [{'hour': int(item['hour']), 'volume': item['volume']} for item in peak_hours_qs]

    # Compose stats dict
    stats = {
        'total_revenue_number': total_revenue,
        'total_bookings': total_bookings_count,
        'cancellation_rate': cancellation_rate,
        'popular_movies': list(popular_movies),
        'busiest_theaters': busiest_theaters,
        'daily_revenue': list(daily_revenue),
        'peak_hours': peak_hours
    }

    # Cache for 5 minutes
    cache.set('admin_dashboard_stats', stats, timeout=300)

    return render(request, 'movies/admin_dashboard.html', {'stats': stats})