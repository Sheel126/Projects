from django.core.serializers import serialize
from django.http import JsonResponse
from .models import Activity, Categories, File
import json
import datetime
from .forms import UploadFileForm


# Before an activity can be created, a file associated with that activity needs to be created
def createFile(request):
    print(request.POST)
    print(request.FILES.get('file'))
    
    form = UploadFileForm(request.POST, request.FILES)
    if form.is_valid():
        instance = File(file=request.FILES["file"])
        instance.save()
        print(instance.id)
        return instance.id
    else:
        print("Form is not valid")
        for field in form: 
            print("Field Error:", field.name,  field.errors)
        return -1


# Call this function if something goes wrong with the activity creation and 
# the uploaded file needs to be deleted
def deleteFile(pkNum):
    print("pkNum")
    print(pkNum)
    allFiles = File.objects.all()
    for obj in allFiles:
        print(f"Id: {obj.id}")
    pkNum = int(pkNum)
    file_To_Delete = File.objects.filter(id=pkNum).first()
    file_To_Delete.delete()


TITLEMAX = 200
DESCRIPTIONMAX = 1000
OBJECTIVEMAX = 200

def createActivity(request):
    data = json.loads(request.body)
    print(data)
    activity_types = ["MM", "JS", "CS", "ST", "PB", "SC", "EL", "DT", "FA", "LC", "RM", "NA", ""]
    # Break the request up into activity fields
    activityCreator = request.user
    titleString = data.get('title')
    descriptionString = data.get('description')
    tensionVal = data.get('tensionAmount') or 0
    targetString = data.get('targetDiscipline')
    levelsString = data.get('educationLevel')
    activityTypeString = data.get('activityType')
    classString = data.get('classSize')
    durationString = data.get('duration')
    activityFormat = data.get('activityFormat')
    fileId = data.get('fileId')
    imageId = data.get('imageId')
    
    # print(activityCreator)
    # print(titleString)
    # print(descriptionString)
    # print(tensionVal)
    # print(targetString)
    # print(levelsString)
    # print(activityTypeString)
    # print(classString)
    # print(durationString)
    # print(activityFormat)
    # print(fileId)
    # print(imageId)

    # Category fields
    environmentVal = data.get('Environment') or 0
    socialVal = data.get('Social') or 0
    economyVal = data.get('Economy') or 0
    
    curiosityVal = data.get('Curiosity') or 0
    connectionsVal = data.get('Connections') or 0
    creatingVal = data.get('Creating Value') or 0
    
    pillarObjectiveVal = data.get('pillarObjective') or ""
    entreObjectiveVal = data.get('entrepreneurialObjective') or ""

    # After breaking it up, process each one and make sure it is valid, 
    # if something is wrong, return False up to the API
    isValidParams = True
    if (len(titleString) > TITLEMAX or len(titleString) == 0): 
        isValidParams = False
    if (len(descriptionString) > DESCRIPTIONMAX or len(descriptionString) == 0):
        isValidParams = False
    if (len(descriptionString) > DESCRIPTIONMAX):
        isValidParams = False
    if (len(pillarObjectiveVal) > OBJECTIVEMAX or len(entreObjectiveVal) > OBJECTIVEMAX):
        isValidParams = False
    if (tensionVal < 0 or tensionVal > 100):
        isValidParams = False
    if (environmentVal < 0 or environmentVal > 100):
        isValidParams = False
    if (socialVal < 0 or socialVal > 100):
        isValidParams = False
    if (economyVal < 0 or economyVal > 100): 
        isValidParams = False
    if (curiosityVal < 0 or curiosityVal > 100):
        isValidParams = False
    if (connectionsVal < 0 or connectionsVal > 100):
        isValidParams = False
    if (creatingVal < 0 or creatingVal > 100): 
        isValidParams = False
    if (activityTypeString not in activity_types):
        isValidParams = False
    
    if (not isValidParams):
        deleteFile(fileId)
        deleteFile(imageId)
        return False
    
    # Detect blank tag values
    if (targetString == ""):
        targetString = 'NO'
    if (levelsString == ""):
        levelsString = "NO"
    if (activityTypeString == ""):
        activityTypeString = "NO"
    if (classString == ""):
        classString = "NO"
    if (durationString == ""):
        durationString = "NO"
    if (activityFormat == ""):
        activityFormat = "NO"

    # Ensure the file with matching fileId exists
    try:
        File.objects.get(pk=fileId)
        File.objects.get(pk=imageId)
    except File.DoesNotExist:
        print('There is no matching file')
        return False

    # Create the categories object & save it
    new_Categories = object()
    try: 
        new_Categories = Categories(
            social = socialVal,
            environment = environmentVal,
            economic = economyVal,
            create = creatingVal,
            curious = curiosityVal,
            connection = connectionsVal,
            pillarsObjective = pillarObjectiveVal,
            targetEMObjective = entreObjectiveVal
        )
        new_Categories.full_clean()
        new_Categories.save()
    except Exception as e:
        print(e)
        deleteFile(fileId)
        deleteFile(imageId)
        return False

    # Create the activity object & Save it to the database
    try:
        new_Activity = Activity(
            creator = activityCreator,
            categories = new_Categories,
            title = titleString,
            description = descriptionString,
            tension = tensionVal,
            target = targetString,
            levels = levelsString,
            activityType = activityTypeString,
            classSize = classString,
            duration = durationString,
            format = activityFormat,
            isApproved = False,
            creationDate = datetime.date.today()
        )
        new_Activity.full_clean()
        new_Activity.save()
        new_Activity.files.add(fileId)
        new_Activity.files.add(imageId)
    except Exception as e: 
        print(e)
        new_Categories.delete() # Delete categories object and file object if activity object creation fails
        deleteFile(imageId)
        deleteFile(fileId)
        return False

    return True


# If this method is called, then authentication has already been checked on the
# backend, and the user has the admin permission to approve Activities
def approveActivity(request):
    # Pull the ActivityID from the request, and then get that
    # Activity object from the database
    ActivityID = request.Activity
    activity = Activity.objects.get(pk=ActivityID)

    # Update the Activity Object and save it
    activity.updateStatus(True)
    activity.save()

# Only Admins and Authors are allowed to edit Activities
# Which should be authenticated by this point
def editActivity(request):
    # Get the edited field
    ActivityID = request.Activity
    # Verify field is valid
    activity = Activity.objects.get(pk=ActivityID)
    # Update Activity Field and Save new instance
    activity.save()

def getPendingActivities(request):
    activities = Activity.objects.filter(isApproved=False)
    data = [
        {
            "title": activity.title,
            "id": activity.id,
            "creator": {
                "id": activity.creator.id,
                "username": activity.creator.username,
                "email": activity.creator.email,
            },
            "creationDate": activity.creationDate
        }
        for activity in activities
    ]
    return JsonResponse({"pendingActivities": data}, safe=False)
    
# Return the Activity object with the given id
def getActivity(requestedActId):
    try:
        return Activity.objects.get(id=requestedActId)
    except Activity.DoesNotExist:
        return None