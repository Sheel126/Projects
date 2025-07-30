# Holds the unit tests for the backend
from sqlite3 import IntegrityError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from rest_framework import status
from app import views
from app import userManager
from django.contrib.auth.models import User, Group
from .models import AboutPageSection, Activity, Categories, File
from django.test import Client
import json
from django.contrib.sessions.middleware import SessionMiddleware
import tempfile
import os
from django.urls import reverse
from django.conf import settings
from PIL import Image
from django.db import connection
from django.core.management import call_command
from django.test import TransactionTestCase
from django.db import transaction

#Create APIRequestFactory Instance
factory = APIRequestFactory()

# Adds middleware to APIRequestFactory for requests that require django's auth system
class SessionRequiredTestMixin(TransactionTestCase):

    def add_session(self, request):
        """Add session object to request by using SessionMiddleware."""
        middleware = SessionMiddleware(request)
        middleware.process_request(request)
        request.session.save()


#Tests the 'register_view' function in views.py
class TestRegister(TestCase, TransactionTestCase):

    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()

    # Test a valid registration
    def test_valid_registration(self):
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        newUser = User.objects.get(email="dsgratta@ncsu.edu") 
        self.assertEqual(newUser.check_password("1234567"), True) # Password is saved

        # Make sure it works with multiple users
        request2 = factory.post('api/register/', {
            'email':'bbbumble@ncsu.edu',
            'password':'2345678'
        }, format='json')
        response2 = views.register_view(request2)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        responseData2 = json.loads(response2.content)
        self.assertEqual(responseData2['message'], 'User registered successfully!')
        self.assertEqual(User.objects.count(), 2)
        newUser2 = User.objects.get(email="bbbumble@ncsu.edu")
        self.assertEqual(newUser2.email, "bbbumble@ncsu.edu")
        self.assertEqual(newUser2.check_password("2345678"), True)

    # Invalid registration with no email
    def test_no_username(self):
        request = factory.post('api/register/', {
            'email':'',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Email and password are required.') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

    
    # Invalid registration with no password 
    def test_no_password(self):
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':''
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Email and password are required.') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

    # Registration with invalid email pattern
    def test_faulty_email(self):
        request = factory.post('api/register/', { # No @ sign in email
            'email':'dsgrattancsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Email format is incorrect.') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

        request2 = factory.post('api/register/', { # Too many @ signs
            'email':'dsgr@atta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response2 = views.register_view(request)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST) 
        responseData2 = json.loads(response2.content) 
        self.assertEqual(responseData2['message'], 'Email format is incorrect.') 
        self.assertEqual(User.objects.count(), 0) 

        request3 = factory.post('api/register/', { # Nothing before first @ sign
            'email':'@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response3 = views.register_view(request)
        self.assertEqual(response3.status_code, status.HTTP_400_BAD_REQUEST) 
        responseData3 = json.loads(response3.content) 
        self.assertEqual(responseData3['message'], 'Email format is incorrect.') 
        self.assertEqual(User.objects.count(), 0) 

        request4 = factory.post('api/register/', { # Integer email
            'email':80808080,
            'password':'1234567'
        }, format='json')
        response4 = views.register_view(request)
        self.assertEqual(response4.status_code, status.HTTP_400_BAD_REQUEST) 
        responseData4 = json.loads(response4.content) 
        self.assertEqual(responseData4['message'], 'Email format is incorrect.') 
        self.assertEqual(User.objects.count(), 0) 

    # Invalid registration with invalid password type
    def test_faulty_password(self):
        request = factory.post('api/register/', { # Integer password
            'email':'dsgratta@ncsu.edu',
            'password':1234567
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Invalid JSON data') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

    # Incorrect/nonexistent request body structuring 
    def test_invalid_json(self):
        request = factory.post('api/register/', {}, format='json') # Empty request body
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Email and password are required.') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

        request = factory.post('api/register/', format='json') # No request body
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Invalid JSON data') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

        request = factory.post('api/register/', { # No json format
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }) 
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response code
        responseData = json.loads(response.content) 
        self.assertEqual(responseData['message'], 'Invalid JSON data') # Response message
        self.assertEqual(User.objects.count(), 0) # Doesn't save user

    # Invalid registration where email is already in database
    def test_user_exists(self):
        request = factory.post('api/register/', { # Add a user to the database
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Check that user was correctly made
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') 
        self.assertEqual(User.objects.count(), 1) 
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') 
        newUser = User.objects.get(email="dsgratta@ncsu.edu") 
        self.assertEqual(newUser.check_password("1234567"), True) 

        request = factory.post('api/register/', { # Add another user with the same email, different password (fail)
            'email':'dsgratta@ncsu.edu',
            'password':'44444444rrrrrrr'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST) # Response codedd
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User already exists with this email.') # Response message
        self.assertEqual(User.objects.count(), 1) # Should still only be one user
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # with these fields
        newUser = User.objects.get(email="dsgratta@ncsu.edu") 
        self.assertEqual(newUser.check_password("1234567"), True) 

        request = factory.post('api/register/', { # Add another user with the same password, different email (success)
            'email':'ertyhyu@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Check that user was correctly added
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') 
        self.assertEqual(User.objects.count(), 2) # Should be two users now
        newUser = User.objects.get(email="ertyhyu@ncsu.edu") 
        self.assertEqual(newUser.email, 'ertyhyu@ncsu.edu') 
        self.assertEqual(newUser.check_password("1234567"), True) 

    # Invalid http method used 
    def test_invalid_methodtype(self):
        request = factory.get('api/register/')  # GET
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED) # Response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid request method') # Response message

        request = factory.put('api/register/', { # PUT
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED) # Response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid request method') # Response message

    

#Tests the 'login_view' function in views.py
# TODO Maybe try logging in a superuser/staff
# TODO Test CSRF Cookie
class TestLogin(TestCase, SessionRequiredTestMixin, TransactionTestCase):
            
    # Initializes test with a user
    def setUp(self):
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        views.register_view(request)

    # Successfully log in a user that's in the database
    def test_valid_user(self):
        request = factory.post('/api/login/', {
            'userId':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        self.add_session(request)
        response = views.login_view(request)
        responseData = json.loads(response.content)
        #print(responseData['message'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(responseData['message'], 'Successfully Logged In')
        self.assertEqual(responseData['Staff'], False)
        self.assertEqual(responseData['Superuser'], False)
        
    # Tries to log in user that doesn't exist
    def test_missing_user(self):
        request = factory.post('api/login/', {
            'userId':'billlll@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

    # Missing email - treats like user doesn't exist
    def test_no_email(self):
        request = factory.post('api/login/', {
            'userId':'',
            'password':'1234567'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

    # Missing password - treats like wrong password
    def test_no_password(self):
        request = factory.post('api/login/', {
            'userId':'dsgratta@ncsu.edu',
            'password':''
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

    # Matching email but wrong password
    def test_wrong_password(self):
        request = factory.post('api/login/', {
            'userId':'dsgratta@ncsu.edu',
            'password':'6789'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

    # Matching password but wrong email
    def test_wrong_email(self):
        request = factory.post('api/login/', {
            'userId':'tyoeour@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

    # Incorrect/nonexistent request body structuring 
    def test_invalid_json(self):
        request = factory.post('api/login/', { # No email 
            'password':'1234567'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

        request = factory.post('api/login/', { # No password
            'email':'dsgratta@ncsu.edu'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login')

        request = factory.post('api/login/', { # No Json specifier
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        })
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid JSON')

        request = factory.post('api/login/', format='json') # No request body
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid JSON')

        request = factory.post('api/login/', {}, format='json') # Empty request body
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid login') # Response message

    # Invalid http method used 
    def test_invalid_methodtype(self):
        request = factory.put('api/login/', { # PUT
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.login_view(request)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED) # Response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'Invalid request method') # Response message



class TestFileUpload(TestCase, SessionRequiredTestMixin, TransactionTestCase):
    
    # Set state to logged in
    def setUp(self):
        self.rq = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        client = Client()
        client.force_login(self.user)
    
    # Test with valid file upload
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_valid_file_upload(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')
            request.user = self.user
            response = views.fileEndpoint(request)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 1)

    # Test with file types that shouldn't be allowed
    # @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    # def test_invalid_filetype(self):
    #     self.fail()

    # Test with invalid file endpoint method call type
    def test_invalid_file_upload_method(self):
        request = self.rq.get('/api/files/')
        request.user = self.user
        response = views.fileEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(File.objects.count(), 0)



class TestLogout(TestCase, SessionRequiredTestMixin):
    # Initializes test with a user
    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()

        self.rq = APIRequestFactory()
        
        # Create a logged in admin to call functions with
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)

#     # Valid logout case 
    def test_valid_logout(self):
        request = factory.post('api/logout/', {

        }, format='json')
        request.user = self.adminUser
        self.add_session(request)
        response = views.logoutUser(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

#     # Invalid json 

#     # Invalid method type
INVALID_TITLE = """Invalid title wayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    too long"""
INVALID_DESCRIPTION = """Invalid description wayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyywayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyywayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyywayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyywayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyywayyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
    yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy too long"""
class TestActivity(TestCase, SessionRequiredTestMixin, TransactionTestCase):

    # Set state to logged in
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def setUp(self):
        self.rq = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        client = Client()
        client.force_login(self.user)

        # Upload file to test with
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')
            
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img_file:
                img = Image.new('RGB', (100, 100), color='red')  # Create a simple red image
                img.save(temp_img_file, format='PNG')
                temp_img_file.seek(0)

                # Posting image file
                request_img = self.rq.post('/api/files/', {'file': temp_img_file, 'title': "Img File"}, format='multipart')
                # request = self.rq.post('/api/files/', 
                #                {'file': [temp_file, temp_img_file], 'title': ["New File", "Img File"]}, 
                #                format='multipart')


            request.user = self.user
            request_img.user = self.user
            response = views.fileEndpoint(request)
            response_img = views.fileEndpoint(request_img)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response_img.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 2)
            self.fileId = File.objects.first().id
            self.imgId = File.objects.last().id
            self.assertIsNotNone(self.fileId)
            print("File Id")
            print(self.fileId)
            print("Image Id")
            print(self.imgId)

        self.activityData = {
            'title': 'Valid title',
            'description': 'Valid description',
            'tensionAmount': 30,
            'targetDiscipline':'AG',
            'educationLevel':'FR',
            'activityType':'MM',
            'classSize':'LA',
            'duration':'SE',
            'activityFormat':'IP',
            'Environment':30,
            'Social': 40,
            'Economy':30,
            'Curiosity':30,
            'Connections':40,
            'Creating Value':30,
            'Empathy':10,
            'Define':10,
            'Ideate':10,
            'Prototype':10,
            'Implement':10,
            'Assess': 50,
            'pillarObjective':'Valid pillar objectives',
            'entrepreneurialObjective':'Valid entreprenurial objective',
            'targetPhaseObjective':'Valid target phase objectives',
            'fileId': self.fileId,
            'imageId': self.imgId
        }
        
    # Test a valid activity creation
    def test_valid_activity(self):
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        # print(responseData['error'])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)

    
    # Invalid title max length
    def test_title_too_long(self):
        self.activityData["title"] = INVALID_TITLE
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid description max length 
    def test_description_too_long(self):
        self.activityData["description"] = INVALID_DESCRIPTION
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid blank title
    def test_blank_title(self):
        self.activityData["title"] = ""
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Valid blank description
    def test_blank_description(self):
        self.activityData["description"] = ""
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid no user given 
    def test_activity_no_user(self):
        request = self.rq.post('api/activities/', self.activityData, format='json')
        # No user 
        # Should throw an error 
        with self.assertRaises(AttributeError):
            views.activityEndpoint(request)
        

    # Invalid Negative tension amount
    def test_negative_tension(self):
        self.activityData["tensionAmount"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid tension too high
    def test_too_much_tension(self):
        self.activityData["tensionAmount"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid target value 
    def test_invalid_target_val(self):
        self.activityData["targetDiscipline"] = "XX" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Blank target value
    def test_blank_target_val(self):
        self.activityData["targetDiscipline"] = "" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)

    # Invalid levels value 
    def test_invalid_levels_val(self):
        self.activityData["educationLevel"] = "XX"
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Blank levels value
    def test_blank_levels_val(self):
        self.activityData["educationLevel"] = "" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        newActivity = Activity.objects.get(title = "Valid title")
        self.assertEqual(newActivity.get_levels_display(), "None")
        self.assertEqual(newActivity.get_target_display(), "Agriculture & Life Science")
        self.assertEqual(File.objects.count(), 2)

    # Invalid activity type value 
    def test_invalid_type_val(self):
        self.activityData["activityType"] = "XX"
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Blank activity type value
    def test_blank_type_val(self):
        self.activityData["activityType"] = "" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)

    # Invalid class size value 
    def test_invalid_size_val(self):
        self.activityData["classSize"] = "XX"
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Blank class value
    def test_blank_size_val(self):
        self.activityData["classSize"] = "" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)

    # Invalid duration value 
    def test_invalid_duration_val(self):
        self.activityData["duration"] = "XX"
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Blank duration value
    def test_blank_duration_val(self):
        self.activityData["duration"] = "" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)

    # Invalid format value 
    def test_invalid_format_val(self):
        self.activityData["activityFormat"] = "XX"
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Blank format value
    def test_blank_format_val(self):
        self.activityData["activityFormat"] = "" 
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)
        

    # Invalid environmental val >100
    def test_invalid_environmental_val(self):
        self.activityData["Environment"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid negative envionmental val
    def test_negative_environmental_val(self):
        self.activityData["Environment"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)     
        self.assertEqual(File.objects.count(), 0)   

    # Invalid social val >100
    def test_invalid_social_val(self):
        self.activityData["Social"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid negative social val
    def test_negative_social_val(self):
        self.activityData["Social"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid economy val >100
    def test_invalid_economy_val(self):
        self.activityData["Economy"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid negative economy val
    def test_negative_economy_val(self):
        self.activityData["Economy"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid curiosity val >100
    def test_invalid_curiosity_val(self):
        self.activityData["Curiosity"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid negative curiosity val
    def test_negative_curiosity_val(self):
        self.activityData["Curiosity"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid connections val >100
    def test_invalid_connections_val(self):
        self.activityData["Connections"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid negative connections val
    def test_negative_connections_val(self):
        self.activityData["Connections"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid creating val >100
    def test_invalid_creating_val(self):
        self.activityData["Creating Value"] = 101
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid negative creating val
    def test_invalid_creating_val(self):
        self.activityData["Creating Value"] = -1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)

    # Invalid pillars objective too long
    def test_pillars_objective_too_long(self):
        self.activityData["pillarObjective"] = INVALID_TITLE
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)


    # Invalid entrepreneurial objective too long
    def test_entre_objective_too_long(self):
        self.activityData["entrepreneurialObjective"] = INVALID_TITLE
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.user
        response = views.activityEndpoint(request)
        responseData = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(responseData['error'], 'Invalid activity data')
        self.assertEqual(Activity.objects.count(), 0)
        self.assertEqual(Categories.objects.count(), 0)
        self.assertEqual(File.objects.count(), 0)


class TestFileInfo(SessionRequiredTestMixin, TransactionTestCase):

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE app_file AUTO_INCREMENT = 1")

        self.rq = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        client = Client()
        client.force_login(self.user)
    
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_get_file_info(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.name = "sample"
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')
            request.user = self.user
            response = views.fileEndpoint(request)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 1)
            self.assertEqual(File.objects.first().id, 1)
        
        response = self.client.get('/api/file-info/1/')
        data = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(data['file_id'], 1)
        self.assertEqual(data['file_name'], 'sample')
        self.assertEqual(data['file_type'], 'uploads/sample')


class TestFileDownload(SessionRequiredTestMixin, TransactionTestCase):
    # Set state to logged in
    def setUp(self):

        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE app_file AUTO_INCREMENT = 1")

        self.rq = APIRequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        client = Client()
        client.force_login(self.user)     
    
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_valid_file_download(self):
        # First upload a file (code from test_valid_file_upload)
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.name = "sample"
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')
            request.user = self.user
            response = views.fileEndpoint(request)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 1)
            self.assertEqual(File.objects.first().id, 1)

        # Then call endpoint
        response = self.client.get('/api/download/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="uploads/sample"')

    # Try (and fail) to download a file that does not exist
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_file_download_dne(self):
        # First upload a file (code from test_valid_file_upload)
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.name = "sample"
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')
            request.user = self.user
            response = views.fileEndpoint(request)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 1)
            self.assertEqual(File.objects.first().id, 1)

        # Then call endpoint
        response = self.client.get('/api/download/2/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)



class TestAdminUpgrade(TestCase, SessionRequiredTestMixin, TransactionTestCase):
    # Set up tests with new user to upgrade (same code as test_valid_registration)
    def setUp(self):

        # Clean up any existing users and set up the test environment
        User.objects.filter(email='hello@ncsu.edu').delete()
        
        # Set up the request factory and create a test user
        self.rq = APIRequestFactory()
        
        # Register a new user (dsgratta@ncsu.edu)
        request = self.rq.post('api/register/', {
            'email': 'dsgratta@ncsu.edu',
            'password': '1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.newUser = User.objects.get(email="dsgratta@ncsu.edu")
        self.assertEqual(self.newUser.check_password("1234567"), True)
        
        # Create another user to be upgraded
        self.otherUser = User.objects.create_user(email="otheruser@ncsu.edu", username="otheruser@ncsu.edu", password="password123")
        
        # Log in as the admin user (make the new user an admin)
        self.newUser.is_staff = True  # Make the user an admin
        self.newUser.save()
        self.client = Client()
        self.client.force_login(self.newUser)
        
    # Use the upgrade to admin function with a pending user
    def test_valid_pending_to_admin(self):
        userManager.upgradeToAdmin(self.newUser)
        self.assertEqual("Administrator", self.newUser.groups.first().name)
        self.assertEqual(User.objects.count(), 2) # One object in database

    # TODO: Uncomment this test once the upgradeToAdmin function is ready to be used in the app
    # Try to upgrade a user that's  an admin
    def test_upgrade_admin_to_admin(self):
        userManager.upgradeToAdmin(self.newUser)
        self.assertEqual("Administrator", self.newUser.groups.first().name)
        self.assertEqual(User.objects.count(), 2) # One object in database

    #     # Do it again and make sure nothing changes
        # userManager.upgradeToAdmin(self.newUser)
        # self.assertEqual("Administrator", self.newUser.groups.first().name)
        # self.assertEqual(User.objects.count(), 1) # One object in database

    def test_make_admin(self):
        request = self.rq.post('/api/makeAdmin', {
        }, format='json')
        request.user = self.newUser  # Set the user as an admin
        response = views.makeAdmin(request)

        # Assert that the response status is 201 (success) and the message is correct
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['message'], 'User Upgraded!')

        # Ensure that the other user is now an admin
        self.newUser.refresh_from_db()
        self.assertTrue(self.newUser.is_staff)
           
    # TODO: Uncomment and write this test once the upgradeToAdmin function is ready to be used in the app
    # Try to upgrade a user that's an educator
    # def test_upgrade_educator_to_admin(self):
    #     self.fail()

class TestDebuggingUser(TestCase):

    def setUp(self):
        # Set up the request factory and create users with groups
        self.rq = APIRequestFactory()
        
        # Register a new admin user
        request = self.rq.post('api/register/', {
            'email': 'dsgratta@ncsu.edu',
            'password': '1234567'
        }, format='json')
        response = views.register_view(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu")
        self.adminUser.set_password("1234567")
        self.adminUser.save()

        # Create some groups
        self.admin_group = Group.objects.create(name='Admin')
        self.member_group = Group.objects.create(name='Member')

        # Assign groups to the user
        self.adminUser.groups.add(self.admin_group, self.member_group)
        
        # Log in the admin user
        self.client = Client()
        self.client.force_login(self.adminUser)

    def test_debugging_user_authenticated(self):
        # Test for an authenticated user with groups
        request = self.rq.get('/api/debuggingUser', format='json')
        request.user = self.adminUser
        response = views.debuggingUser(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        
        # Check the username, auth status, and groups
        self.assertEqual(response_data['message'], self.adminUser.username)
        self.assertTrue(response_data['auth'])
        self.assertIn('Admin', response_data['groups'])
        self.assertIn('Member', response_data['groups'])
    
    def test_debugging_user_unauthenticated(self):
        # Test for an unauthenticated user
        unauthenticated_user = User.objects.create_user(email="nonadmin@ncsu.edu", username="nonadmin@ncsu.edu", password="password123")
        request = self.rq.get('/api/debuggingUser', format='json')
        request.user = unauthenticated_user  # Log in as a different user
        response = views.debuggingUser(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        
        # Check the username, auth status, and groups
        self.assertEqual(response_data['message'], unauthenticated_user.username)
        self.assertTrue(response_data['auth'])
        self.assertEqual(response_data['groups'], [])  # This user has no groups by default

    def test_debugging_user_no_groups(self):
        # Test for a user with no groups assigned
        user_no_groups = User.objects.create_user(email="nousergroups@ncsu.edu", username="nousergroups@ncsu.edu", password="password123")
        request = self.rq.get('/api/debuggingUser', format='json')
        request.user = user_no_groups
        response = views.debuggingUser(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        
        # Check the username, auth status, and groups
        self.assertEqual(response_data['message'], user_no_groups.username)
        self.assertTrue(response_data['auth'])
        self.assertEqual(response_data['groups'], [])  # No groups assigned to this user


class TestImageGeneration(SessionRequiredTestMixin, TransactionTestCase):

    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE app_file AUTO_INCREMENT = 1")

        self.rq = APIRequestFactory()
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)

    def test_image_generation(self):
        request = factory.post('api/files/generate/', {
            'description': 'Dinosaur riding a go kart'
        }, format='json')
        request.user = self.adminUser
        response = views.generateImage(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class TestUserApproval(TestCase, SessionRequiredTestMixin, TransactionTestCase):
    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()
        self.rq = APIRequestFactory()

        # Create a logged in admin to call functions with
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)    

        # Create a new user to test approval with (same code as test_valid_registration)
        request2 = factory.post('api/register/', {
            'email':'dsgratta2@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response2 = views.register_view(request2)
        #print(response.content)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response2.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 2) # Two users in database
        self.newUser = User.objects.get(email="dsgratta2@ncsu.edu") # Save reference to new user
    
    # Successfully approve a new user to educator
    def test_valid_user_approval(self):
        request = factory.post('api/approveUsers/', {
            'pendingApproval': [{'email' : 'dsgratta2@ncsu.edu'}]
        }, format='json')
        request.user = self.adminUser
        response = views.approveUsers(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual("Educator", self.newUser.groups.first().name)

    # TODO: Maybe add test for approving multiple users

    # Invalid test with no user calling endpoint
    def test_invalid_no_user_user_approval(self):
        request = factory.post('api/approveUsers/', {
            'pendingApproval': [{'email' : 'dsgratta2@ncsu.edu'}]
        }, format='json')
        # No user
        # Should throw error
        with self.assertRaises(AttributeError):
            views.approveUsers(request)

    # Invalid test with non-admin user calling endpoint
    def test_invalid_nonAdmin_user_approval(self):
        request = factory.post('api/approveUsers/', {
            'pendingApproval': [{'email' : 'dsgratta2@ncsu.edu'}]
        }, format='json')
        # User trying to approve themselves
        request.user = self.newUser
        # Should throw error
        with self.assertRaises(Exception):
            views.approveUsers(request)

    # Test with invalid json data
    def test_user_approval_invalid_json(self):
        # No JSON specifier
        request = factory.post('api/approveUsers/', {
            'pendingApproval': [{'email' : 'dsgratta2@ncsu.edu'}]
        })
        request.user = self.adminUser
        response = views.approveUsers(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Empty body
        request = factory.post('api/approveUsers/', {
            
        }, format='json')
        request.user = self.adminUser
        response = views.approveUsers(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Test with invalid user approval api method type
    def test_user_approval_invalid_method(self):
        request = factory.get('api/approveUsers/')
        request.user = self.adminUser
        response = views.approveUsers(request)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class TestAboutPageCreation(SessionRequiredTestMixin, TransactionTestCase):
    
    def setUp(self):
        AboutPageSection.objects.filter(id=1).delete()
        AboutPageSection.objects.filter(id=2).delete()
        self.rq = APIRequestFactory()
        request = factory.post('/api/login/', {
            'userId':'hello@ncsu.edu',
            'password':'pass'
        }, format='json')
        self.adminUser = self.adminUser = User.objects.get(email="hello@ncsu.edu")
        self.add_session(request)
        response = views.login_view(request)
        responseData = json.loads(response.content)
        #print(responseData['message'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(responseData['message'], 'Successfully Logged In')
        self.assertEqual(responseData['Staff'], True)
        self.assertEqual(responseData['Superuser'], True)

    def test_create_about_section(self):
        request = self.rq.post('api/add-about-section', {
        }, format='json')
        request.user = self.adminUser
        response = views.add_about_section(request)
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, status.HTTP_200_OK)    
        self.assertEqual(response_data['status'], 'success')

class TestActivityApproval(SessionRequiredTestMixin, TransactionTestCase):

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()
        with connection.cursor() as cursor:
            #cursor.execute(f"TRUNCATE TABLE app_activity")
            cursor.execute(f"ALTER TABLE app_activity AUTO_INCREMENT = 1")
        self.rq = APIRequestFactory()
        
        # Create a logged in admin to call functions with
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)    

        # Upload file to test with
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img_file:
                img = Image.new('RGB', (100, 100), color='red')  # Create a simple red image
                img.save(temp_img_file, format='PNG')
                temp_img_file.seek(0)

                # Posting image file
                request_img = self.rq.post('/api/files/', {'file': temp_img_file, 'title': "Img File"}, format='multipart')


            request.user = self.adminUser
            request_img.user = self.adminUser
            response = views.fileEndpoint(request)
            response_img = views.fileEndpoint(request_img)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response_img.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 2)
            self.fileId = File.objects.first().id
            self.imgId = File.objects.last().id
            self.assertIsNotNone(self.fileId)
            print("File Id")
            print(self.fileId)
            print("Image Id")
            print(self.imgId)

        # Initialize activity data
        self.activityData = {
            'title': 'Valid title',
            'description': 'Valid description',
            'tensionAmount': 30,
            'targetDiscipline':'AG',
            'educationLevel':'FR',
            'activityType':'MM',
            'classSize':'LA',
            'duration':'SE',
            'activityFormat':'IP',
            'Environment':30,
            'Social': 40,
            'Economy':30,
            'Curiosity':30,
            'Connections':40,
            'Creating Value':30,
            'Empathy':10,
            'Define':10,
            'Ideate':10,
            'Prototype':10,
            'Implement':10,
            'Assess': 50,
            'pillarObjective':'Valid pillar objectives',
            'entrepreneurialObjective':'Valid entreprenurial objective',
            'targetPhaseObjective':'Valid target phase objectives',
            'fileId': self.fileId,
            'imageId': self.imgId
        }

        # Upload activity
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.adminUser
        response = views.activityEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)
        self.assertFalse(Activity.objects.first().isApproved)

        # Activity 2
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.adminUser
        response = views.activityEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.activity_2_id = Activity.objects.last().id
        self.assertFalse(Activity.objects.last().isApproved)
    

    # Successfully approve an activity
    def test_valid_activity_approval(self):
        request = self.rq.post('api/approveActivities/', 
            [{"ActivityID": 1}]
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Activity.objects.first().isApproved)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)

    def test_approve_all_activities(self):
        # Test for approving all activities
        request = self.rq.post('/api/approveAll', {}, format='json')
        request.user = self.adminUser
        response = views.approveAll(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertIn('activities approved', response_data['message'])

        # Verify all activities are approved
        activities = Activity.objects.filter(isApproved=True)
        self.assertEqual(activities.count(), 2)
        self.assertTrue(all(activity.isApproved for activity in activities))

    def test_no_unapproved_activities(self):
        # Test for when no unapproved activities exist
        # Approve all activities first
        Activity.objects.all().update(isApproved=True)

        request = self.rq.post('/api/approveAll', {}, format='json')
        request.user = self.adminUser
        response = views.approveAll(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['message'], '0 activities approved.')

    def test_deny_activity_approval(self):
        activity_id = Activity.objects.first().id
        request = self.rq.delete('api/denyActivity1/1', {}, format='json')
        request.user = self.adminUser
        response = views.denyActivity(request, activity_id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['message'], 'Activity successfully denied')

    def test_deny_nonexistent_activity(self):
        request = self.rq.delete('api/denyActivity1/1', {}, format='json')
        request.user = self.adminUser
        response = views.denyActivity(request, 9999)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Activity not found')
    
    def test_deny_activity_invalid_method(self):
        activity_id = Activity.objects.first().id
        request = self.rq.post('api/denyActivity1/1', {}, format='json')
        request.user = self.adminUser
        response = views.denyActivity(request, activity_id)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid request method')


    # Incorrect approval data formatting
    def test_invalid_activity_approval_formatting(self):
        request = self.rq.post('api/approveActivities/', 
            {"ActivityID": 1}
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Activity.objects.first().isApproved)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)

    # Try to approve an activity that doesn't exist
    def test_invalid_activity_approval_dne(self):
        request = self.rq.post('api/approveActivities/', 
            [{"ActivityID": 3}]
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Activity.objects.first().isApproved)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)

    # Incorrect json formatting
    def test_invalid_activity_approval_json(self):
        request = self.rq.post('api/approveActivities/')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Activity.objects.first().isApproved)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)

    # Incorrect request method
    def test_invalid_activity_approval_method(self):
        request = self.rq.get('api/approveActivities/')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertFalse(Activity.objects.first().isApproved)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)
    
class TestGetActivities(SessionRequiredTestMixin, TransactionTestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def setUp(self):

        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE app_activity AUTO_INCREMENT = 1")

        self.rq = APIRequestFactory()
        
        # Create a logged in admin to call functions with
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)    

        # Upload file to test with
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img_file:
                img = Image.new('RGB', (100, 100), color='red')  # Create a simple red image
                img.save(temp_img_file, format='PNG')
                temp_img_file.seek(0)

                # Posting image file
                request_img = self.rq.post('/api/files/', {'file': temp_img_file, 'title': "Img File"}, format='multipart')

            request.user = self.adminUser
            request_img.user = self.adminUser
            response = views.fileEndpoint(request)
            response_img = views.fileEndpoint(request_img)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response_img.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 2)
            self.fileId = File.objects.first().id
            self.imgId = File.objects.last().id
            self.assertIsNotNone(self.fileId)
            print("File Id")
            print(self.fileId)
            print("Image Id")
            print(self.imgId)

        # Initialize activity data
        self.activityData = {
            'title': 'Valid title',
            'description': 'Valid description',
            'tensionAmount': 30,
            'targetDiscipline':'AG',
            'educationLevel':'FR',
            'activityType':'MM',
            'classSize':'LA',
            'duration':'SE',
            'activityFormat':'IP',
            'Environment':30,
            'Social': 40,
            'Economy':30,
            'Curiosity':30,
            'Connections':40,
            'Creating Value':30,
            'Empathy':10,
            'Define':10,
            'Ideate':10,
            'Prototype':10,
            'Implement':10,
            'Assess': 50,
            'pillarObjective':'Valid pillar objectives',
            'entrepreneurialObjective':'Valid entreprenurial objective',
            'targetPhaseObjective':'Valid target phase objectives',
            'fileId': self.fileId,
            'imageId': self.imgId
        }

        # Upload activity
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.adminUser
        response = views.activityEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)
        self.assertEqual(Activity.objects.first().id, 1)
        self.assertFalse(Activity.objects.first().isApproved)

    # Get an activity
    def test_valid_get_activity(self):
        request = self.rq.get('api/activity/1')
        request.user = self.adminUser
        response = views.getActivity(request, 1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        responseData = json.loads(response.content)
        self.assertEqual(responseData['id'], 1)
        self.assertEqual(responseData['title'], "Valid title")

    # Try to get an activity that doesn't exist
    def test_get_activity_dne(self):
        request = self.rq.get('api/activity/2')
        request.user = self.adminUser
        response = views.getActivity(request, 2)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Test Invalid get activity method type
    def test_get_activity_bad_method(self):
        request = self.rq.post('api/activity/1')
        request.user = self.adminUser
        response = views.getActivity(request, 1)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class TestUserProfileUpdate(SessionRequiredTestMixin, TransactionTestCase):

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()
        self.rq = APIRequestFactory()
        User.objects.filter(email='hello@ncsu.edu').delete()
        self.rq = APIRequestFactory()
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)

    def test_upate_email(self):
        request = self.rq.post('/api/updateProfile', {
            'email': 'newemail123@ncsu.edu'
        }, format='json')
        request.user = self.adminUser
        response = views.updateProfile(request)

        # Check that the response is successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['message'], 'Profile updated successfully')

        # Ensure the email was actually updated
        updated_user = User.objects.get(id=self.adminUser.id)
        self.assertEqual(updated_user.email, 'newemail123@ncsu.edu')
        self.assertEqual(updated_user.username, 'newemail123@ncsu.edu')
    
    def test_invalid_method(self):
        # Test that a method other than POST results in a 405 error
        request = self.rq.get('/api/updateProfile', format='json')  # GET instead of POST
        request.user = self.adminUser
        response = views.updateProfile(request)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid request method')

    def test_email_taken(self):
        # Test if the email already exists in the system
        existing_user = User.objects.create_user(email="takenemail@ncsu.edu", username="takenemail@ncsu.edu", password="1234567")
        existing_user.save()

        request = self.rq.post('/api/updateProfile', {
            'email': 'takenemail@ncsu.edu'
        }, format='json')
        request.user = self.adminUser
        response = views.updateProfile(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Email')

    def test_invalid_json(self):
        # Test with invalid JSON format
        request = self.rq.post('/api/updateProfile', '{email: "invalid"}', content_type='application/json')  # Malformed JSON
        request.user = self.adminUser
        response = views.updateProfile(request)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = json.loads(response.content)
        self.assertTrue('error' in response_data)

    def test_email_unchanged(self):
        # Test that when no email is provided, the current email stays the same
        current_email = self.adminUser.email
        request = self.rq.post('/api/updateProfile', {
            'email': current_email  # Providing the same email
        }, format='json')
        request.user = self.adminUser
        response = views.updateProfile(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['message'], 'Profile updated successfully')

        # Ensure the email remains the same
        self.adminUser.refresh_from_db()
        self.assertEqual(self.adminUser.email, current_email)

class TestChangePassword(SessionRequiredTestMixin, TransactionTestCase):
        
        def setUp(self):
            User.objects.filter(email='hello@ncsu.edu').delete()
            self.rq = APIRequestFactory()
            request = factory.post('api/register/', {
                'email':'dsgratta@ncsu.edu',
                'password':'1234567'
            }, format='json')
            response = views.register_view(request)
            #print(response.content)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
            responseData = json.loads(response.content)
            self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
            self.assertEqual(User.objects.count(), 1) # One object in database
            self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
            self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
            self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
            userManager.upgradeToAdmin(self.adminUser)
            client = Client()
            client.force_login(self.adminUser)
        
        def test_update_password(self):
            request = self.rq.post('/api/changePassword', {
                'currentPass': '1234567',
                'newPass': '1234',
                'confirmPass': '1234'
            }, format='json')
            request.user = self.adminUser
            response = views.changePassword(request)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['message'], 'Password changed successfully!')

            # Verify the password is updated
            self.adminUser.refresh_from_db()
            self.assertTrue(self.adminUser.check_password('1234'))

        def test_password_mismatch(self):
            # Test for password mismatch
            request = self.rq.post('/api/changePassword', {
                'currentPass': '1234567',
                'newPass': '1234',
                'confirmPass': '5678'  # Different confirm password
            }, format='json')
            request.user = self.adminUser
            response = views.changePassword(request)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['error'], 'Match')

        def test_incorrect_current_password(self):
            # Test for incorrect current password
            request = self.rq.post('/api/changePassword', {
                'currentPass': 'wrongpassword',
                'newPass': '1234',
                'confirmPass': '1234'
            }, format='json')
            request.user = self.adminUser
            response = views.changePassword(request)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['error'], 'Current')

        def test_invalid_method(self):
            # Test for invalid method (e.g., GET instead of POST)
            request = self.rq.get('/api/changePassword', format='json')
            request.user = self.adminUser
            response = views.changePassword(request)

            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['error'], 'Invalid request method')

        def test_missing_fields(self):
            # Test for missing fields (e.g., no currentPass)
            request = self.rq.post('/api/changePassword', {
                'newPass': '1234',
                'confirmPass': '1234'
            }, format='json')  # Missing currentPass
            request.user = self.adminUser
            response = views.changePassword(request)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            response_data = json.loads(response.content)
            self.assertTrue('error' in response_data)


class TestActivitySearch(SessionRequiredTestMixin, TransactionTestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def setUp(self):
        User.objects.filter(email='hello@ncsu.edu').delete()
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE app_activity AUTO_INCREMENT = 1")

        self.rq = APIRequestFactory()
        
        # Create a logged in admin to call functions with
        request = factory.post('api/register/', {
            'email':'dsgratta@ncsu.edu',
            'password':'1234567'
        }, format='json')
        response = views.register_view(request)
        #print(response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED) # Correct response code
        responseData = json.loads(response.content)
        self.assertEqual(responseData['message'], 'User registered successfully!') # Correct response message
        self.assertEqual(User.objects.count(), 1) # One object in database
        self.assertEqual(User.objects.get().email, 'dsgratta@ncsu.edu') # Email is saved
        self.adminUser = User.objects.get(email="dsgratta@ncsu.edu") # Save reference to new user
        self.assertEqual(self.adminUser.check_password("1234567"), True) # Password is saved
        userManager.upgradeToAdmin(self.adminUser)
        client = Client()
        client.force_login(self.adminUser)    

        # Upload file to test with
        # For the sake of simplicity, we'll just have all the activities share this one file
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            temp_file.write(b"Hello, world")
            temp_file.seek(0)

            request = self.rq.post('/api/files/', {'file': temp_file, 'title': "New File"}, format='multipart')

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img_file:
                img = Image.new('RGB', (100, 100), color='red')  # Create a simple red image
                img.save(temp_img_file, format='PNG')
                temp_img_file.seek(0)

                # Posting image file
                request_img = self.rq.post('/api/files/', {'file': temp_img_file, 'title': "Img File"}, format='multipart')

            request.user = self.adminUser
            request_img.user = self.adminUser
            response = views.fileEndpoint(request)
            reponse_img = views.fileEndpoint(request_img)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(reponse_img.status_code, status.HTTP_201_CREATED)
            self.assertEqual(File.objects.count(), 2)
            self.fileId = File.objects.first().id
            self.imgId = File.objects.last().id
            self.assertIsNotNone(self.fileId)
            print("File Id")
            print(self.fileId)
            print("Img Id")
            print(self.fileId)

        # Initialize activity 1 data 
        # Focus on Social, Connections, Assess
        self.activityData = {
            'title': 'Valid title 1',
            'description': 'Focus on Social, Connections, Assess',
            'tensionAmount': 30,
            'targetDiscipline':'AG',
            'educationLevel':'FR',
            'activityType':'MM',
            'classSize':'LA',
            'duration':'SE',
            'activityFormat':'IP',
            'Environment':30,
            'Social': 40,
            'Economy':30,
            'Curiosity':30,
            'Connections':40,
            'Creating Value':30,
            'Empathy':10,
            'Define':10,
            'Ideate':10,
            'Prototype':10,
            'Implement':10,
            'Assess': 50,
            'pillarObjective':'Valid pillar objectives',
            'entrepreneurialObjective':'Valid entreprenurial objective',
            'targetPhaseObjective':'Valid target phase objectives',
            'fileId': self.fileId,
            'imageId': self.imgId
        }

        # Upload activity 1
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.adminUser
        response = views.activityEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(Categories.objects.count(), 1)
        self.assertEqual(File.objects.count(), 2)

        # Approve activity 1
        request = self.rq.post('api/approveActivities/', 
            [{"ActivityID": 1}]
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Activity.objects.first().isApproved)

        # Initialize activity 2 data 
        # Focus on Environment, Curiosity, Empathy
        self.activityData = {
            'title': 'Valid title 2',
            'description': 'Focus on Environment, Curiosity, Empathy',
            'tensionAmount': 30,
            'targetDiscipline':'AG',
            'educationLevel':'FR',
            'activityType':'MM',
            'classSize':'LA',
            'duration':'SE',
            'activityFormat':'IP',
            'Environment':50,
            'Social': 25,
            'Economy':25,
            'Curiosity':50,
            'Connections':25,
            'Creating Value':25,
            'Empathy':50,
            'Define':10,
            'Ideate':10,
            'Prototype':10,
            'Implement':10,
            'Assess': 10,
            'pillarObjective':'Valid pillar objectives',
            'entrepreneurialObjective':'Valid entreprenurial objective',
            'targetPhaseObjective':'Valid target phase objectives',
            'fileId': self.fileId,
            'imageId': self.imgId
        }

        # Upload activity 2
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.adminUser
        response = views.activityEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 2)
        self.assertEqual(Categories.objects.count(), 2)
        self.assertEqual(File.objects.count(), 2)

        # Approve activity 2
        request = self.rq.post('api/approveActivities/', 
            [{"ActivityID": 2}]
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Initialize activity 3 data 
        # Focus on Economy, Creating Value, Define
        self.activityData = {
            'title': 'Valid title 3',
            'description': 'Focus on Economy, Creating Value, Define',
            'tensionAmount': 30,
            'targetDiscipline':'AG',
            'educationLevel':'FR',
            'activityType':'MM',
            'classSize':'LA',
            'duration':'SE',
            'activityFormat':'IP',
            'Environment':25,
            'Social': 25,
            'Economy':50,
            'Curiosity':25,
            'Connections':25,
            'Creating Value':50,
            'Empathy':10,
            'Define':50,
            'Ideate':10,
            'Prototype':10,
            'Implement':10,
            'Assess': 10,
            'pillarObjective':'Valid pillar objectives',
            'entrepreneurialObjective':'Valid entreprenurial objective',
            'targetPhaseObjective':'Valid target phase objectives',
            'fileId': self.fileId,
            'imageId': self.imgId
        }

        # Upload activity 3
        request = self.rq.post('api/activities/', self.activityData, format='json')
        request.user = self.adminUser
        response = views.activityEndpoint(request)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Activity.objects.count(), 3)
        self.assertEqual(Categories.objects.count(), 3)
        self.assertEqual(File.objects.count(), 2)

    # Setting search params to environmental, curiosity, and empathy
    # These are the highest values of activity 2, so that should be the first result
    def test_valid_activity_search_env_cur_emp(self):
        # We want to search for all three activities so approve activity 3
        request = self.rq.post('api/approveActivities/', 
            [{"ActivityID": 3}]
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Activity.objects.first().isApproved)
        
        request = self.rq.post('api/search/', {
            'pillar': 'EN',
            'entrepreneurial': 'CU',
            'target': 'EM',
            'name': 'Valid title 2'
        }, format='json')
        request.user = self.adminUser
        response = views.searchActivites(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        responseData = json.loads(response.content) 
        self.assertEqual(len(responseData['list']), 1)
        self.assertEqual(responseData['list'][0]['title'], "Valid title 2")
        #Order of the rest doesn't matter since it's a tie

    # Setting search params to environmental, creating value, and empathy
    # Activity 2 should be first bc it's the highest environmental amt, 
    # but Activity 3 should be second becuase it has the highest creating value amt 
    def test_valid_activity_search_env_val_emp(self):
        # We want to search for all three activities so approve activity 3
        request = self.rq.post('api/approveActivities/', 
            [{"ActivityID": 3}]
        , format='json')
        request.user = self.adminUser
        response = views.approveActivity(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Activity.objects.first().isApproved)
        
        request = self.rq.post('api/search/', {
            'pillar': 'EN',
            'entrepreneurial': 'CV',
            'target': 'EM',
        }, format='json')
        request.user = self.adminUser
        response = views.searchActivites(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        responseData = json.loads(response.content) 
        self.assertEqual(len(responseData['list']), 3)
        self.assertEqual(responseData['list'][0]['title'], "Valid title 1")
        self.assertEqual(responseData['list'][1]['title'], "Valid title 2")

    def test_valid_activity_search_no_unapproved(self):
        # Don't approve activity 3
        request = self.rq.post('api/search/', {
            'pillar': 'EN',
            'entrepreneurial': 'CU',
            'target': 'EM',
            'name': 'Valid title 2'
        }, format='json')
        request.user = self.adminUser
        response = views.searchActivites(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        responseData = json.loads(response.content) 
        self.assertEqual(len(responseData['list']), 1)
        self.assertEqual(responseData['list'][0]['title'], "Valid title 2")

    def test_get_authored_activities(self):
        request = self.rq.get('api/search/', {
            'pillar': 'EN',
            'entrepreneurial': 'CU',
            'target': 'EM',
            'name': 'Valid title 2'
        }, format='json')
        request.user = self.adminUser
        response = views.getAuthoredActivities(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        responseData = json.loads(response.content) 
        self.assertEqual(len(responseData['list']), 2)
        self.assertEqual(responseData['list'][0]['title'], "Valid title 1")
        self.assertEqual(responseData['list'][1]['title'], "Valid title 2")