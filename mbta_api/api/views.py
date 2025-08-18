from django.shortcuts import render
from datetime import datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def current_time(request):
    return Response({'current_time': datetime.now().isoformat()})

@api_view(['GET'])
def health_check(request):
    return Response({'status': 'healthy'})
