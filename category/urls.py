from django.urls import path
from . import views

urlpatterns = [
    path('category/', views.category_list, name='category'),
    path('add/', views.add_category, name='add_category'),
    path('edit/<int:category_id>/', views.edit_category, name='edit_category'),
    path('delete/<int:category_id>/', views.delete_category, name='delete_category'),
    path('toggle/<int:category_id>/', views.toggle_category_status, name='toggle_category_status'),
]
