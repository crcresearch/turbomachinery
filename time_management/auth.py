from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, HttpResponseRedirect
from pr.settings.base import LOGIN_URL
from django.urls import reverse


def login_page(request):
    print "At authenticaiton page"
    if request.method == 'GET':
        return render(request, 'auth/login.html', {})
    else:
	print "Attempting to authenticate"
        # try logging them in
        user = authenticate(request=request, username=request.POST['username'], password=request.POST['password'])
	print "Checking authentication..."
        if user is None:
            print "INCORRECT LOGIN"
            return render(request, 'auth/login.html', {'error': 'Incorrect username/password.'})

	print "Authenticted.  Logging user in..."
        print user
        # otherwise, log them in
        login(request, user)

	print "Valid credentials!  Redirecting..."
        #if 'next' in request.POST:
        #    return HttpResponseRedirect(request.POST['next'])
        #else:
        #    return HttpResponseRedirect(reverse('home'))
	return HttpResponseRedirect('/reports/home/')	


def logout_request(request):
    logout(request)
    return HttpResponseRedirect(LOGIN_URL)
