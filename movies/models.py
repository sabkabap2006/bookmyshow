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
    trailer_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def get_youtube_embed_url(self):
        if not self.trailer_url:
            return None
        pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
        match = re.search(pattern, self.trailer_url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube-nocookie.com/embed/{video_id}"
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rating": float(self.rating),
            "cast": self.cast,
            "description": self.description,
            "genres": [g.name for g in self.genres.all()],
            "languages": [l.name for l in self.languages.all()],
            "trailer_embed_url": self.get_youtube_embed_url(),
        }

    def __str__(self):
        return self.name


class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='theaters')
    time = models.DateTimeField()

    def occupancy_rate(self):
        total_seats = self.seats.count()
        booked_seats = self.seats.filter(is_booked=True).count()
        return round((booked_seats / total_seats * 100), 2) if total_seats else 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "movie": self.movie.name,
            "time": self.time.isoformat(),
            "occupancy_rate": self.occupancy_rate(),
        }

    def __str__(self):
        return f"{self.name} - {self.movie.name} at {self.time}"


class Seat(models.Model):
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='seats')
    seat_number = models.CharField(max_length=10)
    is_booked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.seat_number} in {self.theater.name}"


class Booking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seat = models.OneToOneField(Seat, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='bookings')
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    booked_at = models.DateTimeField(auto_now_add=True, db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user": self.user.username,
            "seat": self.seat.seat_number,
            "movie": self.movie.name,
            "theater": self.theater.name,
            "status": self.status,
            "booked_at": self.booked_at.isoformat(),
        }

    def __str__(self):
        return f"Booking by {self.user.username} for {self.seat.seat_number} at {self.theater.name}"


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('CREATED', 'Created'),
        ('AUTHORIZED', 'Authorized'),
        ('CAPTURED', 'Captured'),
        ('FAILED', 'Failed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    razorpay_order_id = models.CharField(max_length=255, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='CREATED', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user": self.user.username,
            "razorpay_order_id": self.razorpay_order_id,
            "status": self.status,
            "amount": float(self.amount),
            "created_at": self.created_at.isoformat(),
        }

    def __str__(self):
        return f"Payment {self.razorpay_order_id} - {self.status}"