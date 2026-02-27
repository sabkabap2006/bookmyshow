import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from movies.models import Movie, Genre, Language, Theater, Seat
from decimal import Decimal


THEATER_NAMES = [
    'PVR Cinemas', 'INOX', 'Cinepolis', 'Carnival Cinemas', 'Raj Mandir',
    'Miraj Cinemas', 'SRS Cinemas', 'Fun Cinemas', 'Wave Cinemas', 'Mukta A2',
    'Galaxy Theatre', 'Sapphire Screen', 'Star Gold Multiplex', 'Silver City',
    'Metro Cinema', 'Regal Theatre', 'Eros Cinema', 'Liberty Cinema',
    'Minerva Theatre', 'Sterling Cineplex'
]

SEAT_PREFIXES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']


class Command(BaseCommand):
    help = 'Seeds the database with 5000 movies, random theaters, and seats'

    def handle(self, *args, **kwargs):
        genres_list = [
            'Action', 'Comedy', 'Drama', 'Sci-Fi', 'Horror',
            'Romance', 'Thriller', 'Animation', 'Documentary', 'Adventure'
        ]
        languages_list = [
            'English', 'Hindi', 'Spanish', 'French', 'Japanese',
            'Korean', 'German', 'Tamil', 'Telugu', 'Malayalam'
        ]

        with transaction.atomic():
            self.stdout.write('Clearing existing data...')
            Seat.objects.all().delete()
            Theater.objects.all().delete()
            Movie.objects.all().delete()
            Genre.objects.all().delete()
            Language.objects.all().delete()

            genres = [Genre.objects.create(name=name) for name in genres_list]
            languages = [Language.objects.create(name=name) for name in languages_list]

            self.stdout.write('Creating 5000 movies...')
            movies_to_create = []
            for i in range(5000):
                movie = Movie(
                    name=f"Movie {i+1}",
                    rating=Decimal(random.randint(10, 100)) / 10,
                    cast=f"Actor {random.randint(1, 100)}, Actor {random.randint(101, 200)}",
                    description=f"Description for Movie {i+1}.",
                    image="movies/default.jpg"
                )
                movies_to_create.append(movie)

            created_movies = Movie.objects.bulk_create(movies_to_create)

            self.stdout.write('Assigning genres and languages...')
            for movie in created_movies:
                movie.genres.add(*random.sample(genres, k=random.randint(1, 3)))
                movie.languages.add(*random.sample(languages, k=random.randint(1, 2)))

            self.stdout.write('Creating theaters and seats...')
            now = timezone.now()
            theaters_to_create = []
            for movie in created_movies:
                # 1-3 random theaters per movie
                num_theaters = random.randint(1, 3)
                chosen_theaters = random.sample(THEATER_NAMES, k=num_theaters)
                for theater_name in chosen_theaters:
                    show_time = now + timedelta(
                        days=random.randint(0, 14),
                        hours=random.choice([10, 13, 16, 19, 22]),
                        minutes=random.choice([0, 15, 30, 45])
                    )
                    theaters_to_create.append(
                        Theater(name=theater_name, movie=movie, time=show_time)
                    )

            created_theaters = Theater.objects.bulk_create(theaters_to_create)

            self.stdout.write(f'Created {len(created_theaters)} theaters. Now creating seats...')
            seats_to_create = []
            for theater in created_theaters:
                # Each theater gets 40 seats (5 rows x 8 seats)
                num_rows = random.randint(3, 5)
                seats_per_row = 8
                for row_idx in range(num_rows):
                    prefix = SEAT_PREFIXES[row_idx]
                    for seat_num in range(1, seats_per_row + 1):
                        seats_to_create.append(
                            Seat(
                                theater=theater,
                                seat_number=f"{prefix}{seat_num}",
                                is_booked=False
                            )
                        )

                # Batch insert seats every 50000 to avoid memory issues
                if len(seats_to_create) > 50000:
                    Seat.objects.bulk_create(seats_to_create)
                    seats_to_create = []

            if seats_to_create:
                Seat.objects.bulk_create(seats_to_create)

        self.stdout.write(self.style.SUCCESS(
            f'Successfully seeded: 5000 movies, {len(created_theaters)} theaters with seats'
        ))
