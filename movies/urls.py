from django.urls import path, re_path
from . import views
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    path('<int:movie_id>/theaters',views.theater_list,name='theater_list'),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('payment/callback/', views.razorpay_callback, name='razorpay_callback'),
    re_path(r'^payment/webhook/?$', views.razorpay_webhook, name='razorpay_webhook'),
    path('payment/cancel/<str:order_id>/', views.razorpay_cancel, name='razorpay_cancel'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]