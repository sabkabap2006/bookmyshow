from django.db import models
from django.contrib.auth.models import User 
import re


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    def __str__(self):
        return self.name

class Language(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    def __str__(self):
        return self.name

class Movie(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    image = models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3, decimal_places=1, db_index=True)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)
    genres = models.ManyToManyField(Genre, related_name='movies')
    languages = models.ManyToManyField(Language, related_name='movies')
    trailer_url = models.URLField(max_length=500, blank=True, null=True, help_text="YouTube Trailer URL")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def get_youtube_embed_url(self):
        """
        Securely extracts the 11-char YouTube video ID to prevent XSS.
        Returns the safe embed URL or None if invalid.
        """
        if not self.trailer_url:
            return None
            
        # Regex to extract 11-character YouTube video ID from various formats
        pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
        match = re.search(pattern, self.trailer_url)
        
        if match:
            video_id = match.group(1)
            # Restore privacy-enhanced URL to bypass aggressive Safari/AdBlocker tracking blocks 
            return f"https://www.youtube-nocookie.com/embed/{video_id}"
        return None
    
    def get_youtube_watch_url(self):
        """
        Returns the YouTube watch URL for fallback display
        """
        if not self.trailer_url:
            return None
        
        # Extract video ID to reconstruct watch URL
        pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
        match = re.search(pattern, self.trailer_url)
        
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        return None

    def __str__(self):
        return self.name

class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie,on_delete=models.CASCADE,related_name='theaters')
    time= models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):
    theater = models.ForeignKey(Theater,on_delete=models.CASCADE,related_name='seats')
    seat_number = models.CharField(max_length=10)
    is_booked=models.BooleanField(default=False)

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

class Booking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    seat = models.OneToOneField(Seat, on_delete=models.CASCADE)

    # ✅ FIXED: Added related_name
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    # ✅ FIXED: Added related_name
    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )

    booked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'Booking by {self.user.username} for {self.seat.seat_number} at {self.theater.name}'

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('CREATED', 'Created'),
        ('AUTHORIZED', 'Authorized'),
        ('CAPTURED', 'Captured'),
        ('FAILED', 'Failed'),
    )
    # A single payment can represent multiple grouped bookings for the same checkout session
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    razorpay_order_id = models.CharField(max_length=255, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='CREATED', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.razorpay_order_id} - {self.status}"