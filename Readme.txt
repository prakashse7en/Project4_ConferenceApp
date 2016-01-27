P4:Conference Organisation App

1) What is it?
Conference oragnisation app allows users to create conferences, creates sessions 
withing a conference,register for a conference and also it allows the users to view
the conferenc ,sessions and also filters it based on city , time and month etc.

In Addition whenever a new conference/new session is created ,& the corresponding conference 
creator is notified regarding this via email.
User can either add or delete his favourite sessions into his wishlists bag

App link - https://confcentral-1188.appspot.com - (syntax -  https://appid.appspot.com)
App REST api points - https://confcentral-1188.appspot.com/_ah/api/explorer (syntax - https://appid.appspot.com/_ah/api/explorer)

2) Files/Folders Included:

SNO  Name                    Type              Description
-----------------------  (Folder/File)-------------------
			            |--------------|
1    static                 (Folder)      contains javascript files,css,images,fonts etc required for the website
2    templates              (Folder)      contains html files required for the website
3    app.yaml       		 (YAML)       project id ,js path,css path,crons and tasks etc are mentioned here
4    cron.yaml  			 (YAML)       cron jobs are configure here
5    index.yaml     		 (YAML)       auto generated file.composite indexes are auto generated here when 
										  it identifiees queryies in the python file.
6    main.py  		         (File)       contains method for calling static methods like cacheFeaturedSpeaker 
										  defined in conference.py file
7    models.py               (File)       contains ndb model,request,response classes
8    settings.py			 (File)       contains android,ios,web client ids for OAuth authentication
9    utils.py				 (File)       contains helper methods.
10   conference.py			 (File)       contains endpoint methods exposed by conference app is defined here

3)Prequisties and app creation

	i)create a new app in google app engine https://console.developers.google.com/
	ii)click create project and get the project id right below it
	iii)add the project id in app.yaml
	iv) generate client id by following below steps
		*)select api manager in google app engine console(https://console.developers.google.com/)
		*) Select credentials from LHN.Configure Proejct Consent screen before advancing to next steps.
		*)Select "web application" as Application type.
		*) In "Authorized javascript orgins" add (your app)https://confcentral-1188.appspot.com,
			(your local url)http://localhost:5000 .(5000-local app port number )
		*)In "Authorized redirect URIs" add (your app)https://confcentral-1188.appspot.com/oauth2callback,
			(your local url)http://localhost:5000/oauth2callback .(5000-local app port number )
		*)Click create button.
		*) get the client id and add it in settings.py and static/js/app.js file.
	v)download google app engine for pyhton from here -https://cloud.google.com/appengine/docs/python/#download_the_app_engine_sdk_for_python
	vi)In google app engine launcher click file -> Add existing application and select this projects root folder
	vii)click play button and test using browse button or deploy it to google cloud engine using deploy button and test in live.

4)Task 1: Add Sessions to a Conference
	Sessions entity class contains following paramters
		-name,highlights,organizerUserId,speaker,duration,typeOfSession,date,startTime,speakerEmail
	SessionForm ProtoRPC class contains follwing parameters
		-name,highlights,organizerUserId,speaker,duration,typeOfSession,date,startTime,speakerEmail,websafeKey
	SessionForms ProtoRPC class is designed to carry list of sessions
	
	*)createSession(SessionForm, websafeConferenceKey) endpoint -
		logic -
		-------
			- single conference can have multiple sessions so one to many relationship.
			- takes websafe conferce key as input and returns session form
			-using websafe conference key get the data store conference key 
				this conference key is used to genrated relationship with session generate session id using it
				created session is then saved to datastore
			- mandatory fiels for this endpoint is name,speaker,speakerEmail
			- a new session is created with ancestor as conference entity (conference selected based on websafe conference key)
	*)getConferenceSessions(websafeConferenceKey) endpoint - 
		logic -
		--------
			- each session has one conference as ancestor i.e. many to one relationship
			- here web safe conference key of a conference is recived from as input and get the conference key
			- Since Conference is ancestor to the session using ancestor query fetch the corresponding sessions
			- output is a list of sessions i.e more than one sessions
			
	*)getConferenceSessionsByType(websafeConferenceKey, typeOfSession)-
		logic-
		------
			- here session type is taken as input along with the conference key
			- first the corresponding sessions in a conference is fetched
			- then the returned sessions are further filtered with session type specfied in the input
	*)getSessionsBySpeaker(speaker)-
		logic-
		------
			- here speaker name is given as input 
			- get all the sessions and further filter results with speaker given in input
			
5)Task 2: Add Sessions to User Wishlist
	*)addSessionToWishlist(SessionKey) -
		wishlist parameter is added to Profile entiy class and ProtoRPC class 
		logic-
		------
			- provide a session(websafesessionkey) which the user is intreseted.
			-check mentioned session already exist in list of sessions created
			- if exist then append the web safe session key to users wishlist 
	*)getSessionsInWishlist()-
		logic-
		------
			-using the user email id get the profile which inturn used to get the list of websafe sessions key present 
			 in his wishlist bag
			-get the session key using the websafe session key which inturn is used to fetch the actual sessions
	*)deleteSessionInWishlist(SessionKey) -
		logic-
		------
			- provide a session(websafesessionkey) which the user is intreseted to delete from his bag.
			-check mentioned session already exist in list of sessions created
			- if exist then remove the web safe session key to users wishlist 			

6)Task 3: Work on indexes and queries			
	*)Create indexes - autogenerated indexes for sessions 
	*)Come up with 2 additional queries-
		*)getConferenceSessionsByDuration-
			-get dureation and conference in which you need to filter
			-get all the sessions and further filter results with duration given in input 
		*)getSessionsBySpeakerAndMail-
			-get speaker email id and speaker name as input
			-get all the sessions and further filter results with email given in input 
		*)getConfFromSessionsInWishlist-
			-get the profile based on user data
			- fetch all the sessions present in his wishlist based on websafe session key
			-get the parent of each session and display all the conferences for the corresponding 
			 sessions present in user wish list

7)Solve the following query related problem-
App engine datastore supports only one inequality filter to overcome ,we can add two filter not equal to workshop and before seven.
we will retreive all the sessions before seven intially and then iterate over each session and check session type if it is not workshop
session add it to list of sessions endpoints used for the same is - getSessionsBeforeSeven()

8)Task 4: Add a Task
			*)send_session_confirmation_email - send confirmation email to  conference creator when a new session is created
			*)set_featured_speaker - calls _cacheFeaturedSpeaker() which checks this speaker has more than 2 sessions in this 
			  conerence and sets the memcache
9)getFeaturedSpeaker()
	- get the value from memcache if it is not empty ,the speaker name ,email ,sessions he attends and the conference name is
	displayed
	else - no featured speaker is displayed
			

	
	
