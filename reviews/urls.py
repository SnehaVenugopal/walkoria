from django.urls import path, include
from . import views

urlpatterns = [
    path('submit-rating/', views.submit_rating, name='submit_rating'),
    path('get-user-review/<int:product_id>/', views.get_user_review, name='get_user_review'),
]
