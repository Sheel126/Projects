from django.http import JsonResponse, FileResponse
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import AboutPageSection
import json
from app import userManager, activityManager, activitySearcher
from app import settings
from .models import File
from .models import Activity
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, FileResponse
import openai
import requests

# Handles API Calls

@ensure_csrf_cookie
def login_view(request):
    if request.method == "GET":
        # set the CSRF cookie
        return JsonResponse({"message": "CSRF token set"}, status=200)
    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            username = data.get("userId")
            password = data.get("password")
        
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                login(request, user)
                return JsonResponse({"status": "success", "message": "Successfully Logged In", "Staff": user.is_staff, "Superuser": user.is_superuser})
            else:
                return JsonResponse({"status": "error", "message": "Invalid login"}, status=401)
        except json.JSONDecodeError:
            return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)


@csrf_exempt #for now 
def register_view(request):
    if request.method == 'POST':
        try:

            #print(request.body)

            # Parse the incoming JSON data
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')

            # Validate the incoming data
            if not email or not password:
                return JsonResponse({"status": "error", 'message': 'Email and password are required.'}, status=400)
            
            try:
                validate_email(email)
            except ValidationError:
                return JsonResponse({"status": "error", 'message': 'Email format is incorrect.'}, status=400)
            
            if (not(isinstance(password, str) or isinstance(password, bytes))):
                return JsonResponse({"status": "error", 'message': 'Invalid JSON data'}, status=400)

            # Check if the user already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({"status": "error", 'message': 'User already exists with this email.'}, status=400)

            # Pass the user information to the userManager to create the new user
            # and update its permissions as a new user
            userManager.registerNewUser(email, make_password(password))

            return JsonResponse({"status": "success", 'message': 'User registered successfully!'}, status=201)
        
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)  
            return JsonResponse({"status": "error", 'message': 'Invalid JSON data'}, status=400)

    return JsonResponse({"status": "error", 'message': 'Invalid request method'}, status=405)


# Allow a user to logout using Django
@ensure_csrf_cookie
@login_required
def logoutUser(request):
    if request.method == 'POST':
        try:
            logout(request)
            return JsonResponse({"message": "User Logged Out"}, status=200)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)  
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def get_about_content(request):
    """API endpoint to get all about page sections"""
    sections = AboutPageSection.objects.all().order_by('order')
    content = {}
    
    for section in sections:
        content[section.section_key] = {
            'title': section.title,
            'body': section.body
        }
    
    return JsonResponse(content)

@csrf_exempt
@user_passes_test(userManager.isAdmin)
def update_about_content(request):
    """API endpoint to update about page content"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method allowed'}, status=405)
    
    if not request.user.is_authenticated or not request.user.groups.filter(name='Administrator').exists():
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        
        # Handle the updated content
        for section_key, section_data in data.items():
            section, created = AboutPageSection.objects.get_or_create(
                section_key=section_key,
                defaults={
                    'title': section_data['title'],
                    'body': section_data['body'],
                    'order': int(section_key.replace('section', ''))
                }
            )
            
            if not created:
                section.title = section_data['title']
                section.body = section_data['body']
                section.save()
        
        # Handle section deletion (sections in DB but not in request)
        existing_keys = AboutPageSection.objects.values_list('section_key', flat=True)
        for key in existing_keys:
            if key not in data:
                AboutPageSection.objects.filter(section_key=key).delete()
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@user_passes_test(userManager.isAdmin)
def add_about_section(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST method allowed'}, status=405)
    
    if not request.user.is_authenticated or not request.user.groups.filter(name='Administrator').exists():
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    try:
        # Get the highest section number
        highest_section = AboutPageSection.objects.all().order_by('-order').first()
        new_order = 1 if not highest_section else highest_section.order + 1
        
        # Create a new section
        new_key = f"section{new_order}"
        AboutPageSection.objects.create(
            section_key=new_key,
            title="New Section Title",
            body="Enter content for this section here.",
            order=new_order
        )
        
        return JsonResponse({'status': 'success', 'sectionKey': new_key}, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


# Endpoint for uploading file
@ensure_csrf_cookie
@login_required
def fileEndpoint(request):
    print('FILE UPLOAD HIT')
    print(request.FILES)
    if request.method == 'POST':
        try:
            fileId = activityManager.createFile(request)
            if (fileId < 0): 
                return JsonResponse({'error' : "Could not construct file"}, status=400)
            return JsonResponse({'status': "success", 'message': 'File created successfully', 'fileId': fileId}, status=201)
        except Exception as e: 
            print(e)
            return JsonResponse({'error' : "Could not construct file"}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Endpoint for interacting with activities
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.canCreate)
def activityEndpoint(request):
    # Try to create a new activity
    if request.method == 'POST':
        try: 
            isActivityCreated = activityManager.createActivity(request)
            if (not isActivityCreated):
                return JsonResponse({'error': 'Invalid activity data'}, status=400)
            return JsonResponse({"status": "success", 'message': 'Activity created successfully!'}, status=201)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)  
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    if request.method == 'GET':
        return activityManager.getPendingActivities(request)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Endpoint for downloading a file
def downloadFile(request, file_id):
    try:
        requested_file = File.objects.get(pk=file_id)

        if requested_file.file.name.endswith(".pdf"):
            content_type = "application/pdf"
        elif requested_file.file.name.endswith((".png", ".jpg", ".jpeg")):
            content_type = "image/jpeg"
        else:
            content_type = "application/octet-stream"

        response = FileResponse(open(requested_file.file.path, "rb"), content_type=content_type)

        if not requested_file.file.name.endswith((".pdf", ".png", ".jpg", ".jpeg")):
            response["Content-Disposition"] = f'attachment; filename="{requested_file.file.name}"'

        return response
    except File.DoesNotExist:
        return JsonResponse({"error": "File not found"}, status=404)

    
# Getting file info
def getFileInfo(request, file_id):
    """ Fetch file name and type based on file_id """
    file_instance = get_object_or_404(File, id=file_id)
    
    return JsonResponse({
        "file_id": file_instance.id,
        "file_name": file_instance.get_file_name(),
        "file_type": file_instance.get_file_extension()
    })


# Generate AI image
def generateImage(request):
    if request.method == "POST":
        data = json.loads(request.body)
        description = data.get("description", "Classroom activity based on sustainability")
        if not description:
            return JsonResponse({"error": "No description provided"}, status=400)

        openai.api_key = settings.OPENAI_API_KEY
        try:
            response = openai.images.generate(
                model="dall-e-3",
                prompt=description,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            image_response = requests.get(image_url, stream=True)
            if image_response.status_code == 200:
                return HttpResponse(image_response.content, content_type="image/png")

            return JsonResponse({"error": "Failed to download image"}, status=500)
            
        except openai.OpenAIError as e:
            print("OpenAI Error:", str(e))
            return JsonResponse({"error": str(e)}, status=500)
        except Exception as e:
            print("Error:", str(e));
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)


@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.isAdmin)
def approveUsers(request):
    # Try to approve the user(s) passed
    if request.method == 'POST':
        print("HIT")
        try:

            # TODO: Verify this is how frontend passes it
            data = json.loads(request.body)

            print(data)

            userArray = data['pendingApproval']

            print(userArray)
            
            errorMessage = "The following User's could not be approved: "
            
            # TODO: Test once frontend is good, need to verify this works with the userManager
            if len(userArray) > 1:
                for i in range(len(userArray)):
                    usersApproved = userManager.approveUser(userArray[i])
                    if usersApproved is None:
                        errorMessage += str(userArray[i]) + ", "
            
            else:
                usersApproved = userManager.approveUser(userArray[0])
                if usersApproved is None:
                        errorMessage += str(userArray[0])
            

            if errorMessage != "The following User's could not be approved: ":
                return JsonResponse({'error': errorMessage}, status=400)
            
            return JsonResponse({"status": "success", 'message': 'User(s) Approved!'}, status=201)
        except json.JSONDecodeError as e:
            print("JSON Decode Error:", e)  
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except KeyError as e:
            print("Keyerror:", e)
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Return the list of pending users to the frontend so that the Admin can review and approve them
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.isAdmin)
def getPendingUsers(request):
    if request.method == 'GET':
        return JsonResponse({"users": userManager.getPendingUsers()}, status=200)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Conduct a search request based on the parameters passed from the frontend
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.canView)
def searchActivites(request):
    # Needs to be post since we are sending data
    if request.method == 'POST':
        data = json.loads(request.body)
        actList = activitySearcher.searchActivitiesWithFilters(data)
        return JsonResponse({'list': actList})
        
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Get a single Activity based on its id number, which is passed in the URL
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.canView)
def getActivity(request, id):
    if request.method == 'GET':
        activity = activityManager.getActivity(id)
        if (activity == None):
            return JsonResponse({'error': 'Activity not found'}, status=404)

        return JsonResponse(activity.to_dict(), safe=False, status=200)

    # Return the found activity as a JSON Response
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Return a list of activities that the current user created
@ensure_csrf_cookie
@login_required
def getAuthoredActivities(request):
    if request.method == 'GET':

        activities = activitySearcher.findAuthoredActivities(request.user)

        return JsonResponse({"list" : activities})

    # Return the found activity as a JSON Response
    return JsonResponse({'error': 'Invalid request method'}, status=405)
  
  
# Handles updates to email and username
@login_required
def updateProfile(request):
    if request.method == 'POST':
        try:
            # Modified to remove Edit Username functionality for reasons explained in the blurb on line 146 of Profile.jsx. 
            # Please go read that block of text before making any changes here. - Reed
    
            data = json.loads(request.body)
            user = request.user
            
            #username = data.get('username', user.username)
            email = data.get('email', user.email)
            print("EMAILLLL", email)

            # Check for existing username or email (excluding current user)
            # Sends error messsages to lines 84 and 86 of Profile.jsx

            # if User.objects.exclude(id=user.id).filter(username=username).exists():
            #    return JsonResponse({'error': 'Username'}, status=400)
            if User.objects.exclude(id=user.id).filter(email=email).exists():
                return JsonResponse({'error': 'Email'}, status=400)

            # Update fields. The login compares username with email entered. Need to change this in the future by making a custom authenticate method.   
            if email:
                user.email = email
                user.username = email
            
            user.save()            

            return JsonResponse({'message': 'Profile updated successfully'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Handles changing the user's password
@login_required
def changePassword(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            currentPass = data.get('currentPass')
            newPass = data.get('newPass')
            confirmPass = data.get('confirmPass')

            # Validate matching passwords
            if newPass != confirmPass:
                return JsonResponse({'error': 'Match'}, status=400)

            # Authenticate user with the current password
            user = request.user
            if not user.check_password(currentPass):
                return JsonResponse({'error': 'Current'}, status=400)

            # Update password
            user.set_password(newPass)
            user.save()
            return JsonResponse({'message': 'Password changed successfully!'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Approve the pending activity, which can only be done by an admin
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.isAdmin)
def approveActivity(request):
    if request.method == 'POST':
        try:
            # Parse the JSON payload from the request body
            data = json.loads(request.body)
            print(data)
            print(type(data))
            # Ensure the payload is a list of activity IDs
            if not isinstance(data, list):
                return JsonResponse({"error": "Expected a list of ActivityID objects"}, status=400)

            # Iterate over the list and approve each activity
            for item in data:
                if not isinstance(item, dict) or "ActivityID" not in item:
                    return JsonResponse({"error": "Invalid data format. Each item must be an object with 'ActivityID'."}, status=400)
                
                activityID = item["ActivityID"]

                # Approve the activity
                try:
                    activity = Activity.objects.get(pk=activityID)
                    activity.updateStatus(True)
                    activity.save()
                except Activity.DoesNotExist:
                    return JsonResponse({"error": f"Activity with ID {activityID} does not exist"}, status=404)

            return JsonResponse({"message": "All activities approved successfully"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)



# Approve all pending activities, which can only be done by an admin
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.isAdmin)
def approveAll(request):
    unapproved_activities = Activity.objects.filter(isApproved=False)
    count = unapproved_activities.update(isApproved=True)

    return JsonResponse({"message": f"{count} activities approved."}, status=200)


# Deny the pending activity, which can only be done by an admin
@ensure_csrf_cookie
@login_required
@user_passes_test(userManager.isAdmin)
def denyActivity(request, id):
    if request.method == 'DELETE':
        activity = activityManager.getActivity(id)
        if (activity == None):
            return JsonResponse({'error': 'Activity not found'}, status=404)

        try:
            activity.delete()
            return JsonResponse({'message': 'Activity successfully denied'}, status=200)
        except:
            return JsonResponse({'error': 'Activity failed to deny'}, status=400)

    # Return the found activity as a JSON Response
    return JsonResponse({'error': 'Invalid request method'}, status=405)


##############################################
#       Methods used for development         #
#       which will be later deleted          #
##############################################


# Make the current user an admin
def makeAdmin(request):
    
    try:
        print(request.user)
        userManager.upgradeToAdmin(request.user)
        return JsonResponse({"status": "success", 'message': 'User Upgraded!'}, status=201)
    except json.JSONDecodeError as e:
        print("JSON Decode Error:", e)  
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    

# Show the current user's status
def debuggingUser(request):
    usern = request.user.get_username()
    auth = request.user.is_authenticated
    group = [group.name for group in request.user.groups.all()]

    return JsonResponse({"message": usern, "auth": auth, "groups": group}, status=200)