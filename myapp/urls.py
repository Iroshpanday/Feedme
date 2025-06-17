from django.urls import path
from .views import TaskListCreate

urlpatterns = [
    path('api/tasks/', TaskListCreate.as_view(), name='task-list'),
]