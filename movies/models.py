from django.db import models
from django.contrib.auth.models import User 

class Movie(models.Model):

    GENRE_CHOICES = [
        ('Action', 'Action'),
        ('Comedy', 'Comedy'),
        ('Drama', 'Drama'),
        ('Horror', 'Horror'),
    ]

    LANGUAGE_CHOICES = [
        ('Hindi', 'Hindi'),
        ('English', 'English'),
        ('Tamil', 'Tamil'),
        ('Telugu', 'Telugu'),
    ]

    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)

    genre = models.CharField(max_length=50, choices=GENRE_CHOICES)
    language = models.CharField(max_length=50, choices=LANGUAGE_CHOICES)
    trailer_url = models.URLField(blank=True, null=True)


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

    # 🔐 NEW FIELDS
    is_reserved = models.BooleanField(default=False)
    reserved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    reserved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

class Booking(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    seat=models.OneToOneField(Seat,on_delete=models.CASCADE)
    movie=models.ForeignKey(Movie,on_delete=models.CASCADE)
    theater=models.ForeignKey(Theater,on_delete=models.CASCADE)

    booked_at = models.DateTimeField(auto_now_add=True)

    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    def __str__(self):
        return f'Booking by{self.user.username} for {self.seat.seat_number} at {self.theater.name}'