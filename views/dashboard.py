from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    """
    WhatsApp dashboard view
    """
    context = {
        'title': 'WhatsApp Dashboard',
    }
    return render(request, 'whatsapp/dashboard.html', context)
