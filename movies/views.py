
import stripe
from django.shortcuts import render, redirect ,get_object_or_404
from .models import Movie,Theater,Seat,Booking
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages


def movie_list(request):
    release_expired_reservations()
    movies = Movie.objects.all()

    search_query = request.GET.get('search')
    genre = request.GET.get('genre')
    language = request.GET.get('language')

    # Search filter
    if search_query:
        movies = movies.filter(name__icontains=search_query)

    # Genre filter
    if genre:
        movies = movies.filter(genre=genre)

    # Language filter
    if language:
        movies = movies.filter(language=language)

    context = {
        'movies': movies
    }

    return render(request, 'movies/movie_list.html', context)


def theater_list(request,movie_id):
    release_expired_reservations()
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})

def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    return render(request, "movies/movie_detail.html", {"movie": movie})


@login_required(login_url='/login/')
def book_seats(request,theater_id):
    # release expired seats first
    release_expired_reservations()
    #reservation_started_at = timezone.now()  # or from DB/session
    
    theaters=get_object_or_404(Theater,id=theater_id)
    seats=Seat.objects.filter(theater=theaters)
    if request.method=='POST':
        selected_Seats= request.POST.getlist('seats')
        error_seats=[]
        if not selected_Seats:
            return render(request,"movies/seat_selection.html",{'theater':theaters,"seats":seats,'error':"Please select at least one seat"})
        for seat_id in selected_Seats:
            seat = get_object_or_404(Seat, id=seat_id, theater=theaters)
            if seat.is_booked:
                return render(request, "movies/seat_selection.html", {
            'theater': theaters,
            'seats': seats,
            'error': f"Seat {seat.seat_number} is already booked"
        })
            
            if seat.is_reserved and seat.reserved_by != request.user:
                messages.error(
                    request,
                    f"Seat {seat.seat_number} is temporarily reserved. Please select another seat."
                      )
                return redirect('book_seats', theater_id=theaters.id)

       
        
    # ✅ ONLY AFTER ALL CHECKS — reserve
        for seat_id in selected_Seats:
            seat = Seat.objects.get(id=seat_id,theater=theaters)
            seat.is_reserved = True
            seat.reserved_by = request.user
            seat.reserved_at = timezone.now()
            seat.save()
            
        # 🔐 store temporarily
        request.session['selected_seats'] = selected_Seats
        request.session['theater_id'] = theaters.id

        request.session['reservation_started_at'] = timezone.now().isoformat()

        request.session.modified = True
        return redirect('create_checkout_session')
    return render(request,'movies/seat_selection.html',{'theaters':theaters,"seats":seats,'reservation_started_at': request.session.get('reservation_started_at')})

    
@login_required
@require_POST
def cancel_booking(request, booking_id):
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

    seat = booking.seat
    seat.is_booked = False
    seat.is_reserved = False
    seat.reserved_by = None
    seat.reserved_at = None
    seat.save()

    booking.delete()
    return redirect('profile')



stripe.api_key = settings.STRIPE_SECRET_KEY
@login_required
def create_checkout_session(request):

    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'inr',
                'product_data': {
                    'name': 'Movie Ticket',
                },
                'unit_amount': 50000,  # 500 rupees (amount in paise)
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url="http://127.0.0.1:8000/movies/payment-success/",
        cancel_url="http://127.0.0.1:8000/movies/payment-failed/",

    )

    return redirect(session.url)


@login_required
def payment_success(request):
    seat_ids = request.session.get('selected_seats')
    theater_id = request.session.get('theater_id')

    if not seat_ids or not theater_id:
        return redirect('movie_list')

    theater = get_object_or_404(Theater, id=theater_id)

    booked_seats = []

    for seat_id in seat_ids:
        seat = get_object_or_404(Seat, id=seat_id, theater=theater)

        if seat.is_booked:
            continue
        if not seat.is_reserved or seat.reserved_by != request.user:
            continue
        if seat.reserved_at < timezone.now() - RESERVATION_TIMEOUT:
            continue

        Booking.objects.create(
            user=request.user,
            seat=seat,
            movie=theater.movie,
            theater=theater,
        )

        seat.is_booked = True
        seat.is_reserved = False
        seat.reserved_by = None
        seat.reserved_at = None
        seat.save()
        booked_seats.append(seat.seat_number)

    # 🧹 clear session
    request.session.pop('selected_seats', None)
    request.session.pop('theater_id', None)

    # 📧 SEND EMAIL NOW (AFTER PAYMENT)
    subject = "Booking Confirmed - BookMySeat"
    message = f"""
    Hi {request.user.username},

    Your payment was successful !
    and Your Booking is Confirmed 🎉

    Movie: {theater.movie.name}
    Theater: {theater.name}
    Seats: {', '.join(booked_seats)}
    Time: {theater.time}

    Enjoy your movie 🍿🎬
    """

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [request.user.email],
        fail_silently=True,
    )

    return render(request, "movies/success.html", {
        "seats": booked_seats,
        "movie": theater.movie,
        "theater": theater
    })


def payment_failed(request):
    seat_ids = request.session.get('selected_seats')

    if seat_ids:
        for seat_id in seat_ids:
            Seat.objects.filter(
                id=seat_id,
                reserved_by=request.user,
                is_booked=False
            ).update(
                is_reserved=False,
                reserved_by=None,
                reserved_at=None
            )

    request.session.pop('selected_seats', None)
    request.session.pop('theater_id', None)

    return render(request, "movies/failed.html")



RESERVATION_TIMEOUT = timedelta(minutes=5)
def release_expired_reservations():
    expiry_time = timezone.now() - RESERVATION_TIMEOUT
    Seat.objects.filter(
        is_reserved=True,
        reserved_at__lt=expiry_time,
        is_booked=False
    ).update(
        is_reserved=False,
        reserved_by=None,
        reserved_at=None
    )





    




