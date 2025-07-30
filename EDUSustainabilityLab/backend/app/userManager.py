from django.contrib.auth.models import User
from django.contrib.auth.models import Group, Permission

# Author: Caleb Twigg (wctwigg)
#   -> registerNewUser: Register a new user and add them to the database
#   -> getPendingUsers: Return a list of all users in the Pending Group
#   -> upgradeToAdmin: Upgrade a single user to admin status
#   -> approveUser: Approve a single user to Pending Status

def isAdmin(user):
    group = user.groups.get_by_natural_key(name='Administrator')
    print("at least called")
    if group is None:
        return False
    else:
        return True

# Pending users can not view Activities on the platform
def canView(user):
    try:

        group = user.groups.get_by_natural_key(name='Pending')
    except:
        return True
    
    if group is None:
        return True
    else:
        return False
    
# Pending users can not create Activities on the platform
def canCreate(user):
    try:

        group = user.groups.get_by_natural_key(name='Pending')
    except:
        return True
    
    if group is None:
        return True
    else:
        return False

# Create a new user object, and ensure that they are added to the Pending User Group
# This will restrict their access before they are officially approved by an administrator
def registerNewUser(email, hashPass):

    # Create the user object and store in the system
    newUser = User.objects.create(
        username=email, 
        email=email,
        password=hashPass,  # Hash the password before storing it
    )
    
    # Either create or get the Pending User Group
    pending_group, created = Group.objects.get_or_create(name='Pending')

    # In case the Group was not created, specify the permissions
    if created:
        permissions = Permission.objects.filter(codename=['pending_view', 'search_public'])
        pending_group.permissions.add(*permissions)

    # Add the user to the group and save
    newUser.groups.add(pending_group)
    newUser.save()
    
    # The views.py code will need the newUser object to send back to the front end
    return newUser

# Get the list of user's that are currently apart of the pending group
# Make sure that only their username, email, and join date is passed, and not the hashed password
def getPendingUsers():
    class publicUser():
        def __init__(self, name, email, joined):
            self.name = name
            self.email = email
            self.joined = joined

        # Method to convert the object to a dictionary
        def to_dict(self):
            return {
                "name": self.name,
                "email": self.email,
                "joined": self.joined
            }

    # Using the pending group, pull all the users in it
    pendingGroup = Group.objects.get(name='Pending')
    pendingUsers = pendingGroup.user_set.all()

    pendingResponse = []

    # Iterate through users and add their dictionary representation to the list
    for user in pendingUsers:
        public_user = publicUser(user.username, user.email, user.date_joined)
        pendingResponse.append(public_user.to_dict())  # Call to_dict() here
        print(user.username)

    # Return the list of pending users
    return pendingResponse

# Upgrade a single user to Admin status
def upgradeToAdmin(user):

    newAdmin = User.objects.get_by_natural_key(user.get_username())

    newAdmin.groups.remove(newAdmin.groups.get(name='Pending'))

    # Either create or get the Admin User Group
    admin_group, created = Group.objects.get_or_create(name='Administrator')

    if created:
        permissions = Permission.objects.filter(codename=['admin'])
        admin_group.permissions.add(*permissions)

    newAdmin.groups.add(admin_group)
    newAdmin.is_staff = True

    newAdmin.save()

    return newAdmin

# Approve a single user to Educator Status
def approveUser(user):

    newUser = User.objects.get_by_natural_key(user['email'])

    # Remove the pending group from the user
    newUser.groups.remove(newUser.groups.get(name='Pending'))

    # Either create or get the Educator User Group
    educator_group, created = Group.objects.get_or_create(name='Educator')

    if created:
        permissions = Permission.objects.filter(codename=['educator'])
        educator_group.permissions.add(*permissions)

     # Add the user to the group and save
    newUser.groups.add(educator_group)
    newUser.save()
    
    # The views.py code will need the newUser object to send back to the front end
    return newUser
