from flask import Flask, request, jsonify
from azure.cosmos import CosmosClient
from msal import ConfidentialClientApplication
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleDefinition
import datetime
import os
import json
import requests


app = Flask(__name__)
ENDPOINT = os.environ.get('cosmosdb_endpoint')
KEY = os.environ.get('cosmosdb_key')
TENANT_ID = os.environ.get('azure_ad_tenant_id')
CLIENT_ID = os.environ.get('azure_ad_client_id')
CLIENT_SECRET = os.environ.get('azure_ad_client_secret')
SCOPE = ['https://database.azure.com/.default']
AUTHORITY_URL = f'https://login.microsoftonline.com/{TENANT_ID}'
USERS_API_URL = 'https://graph.microsoft.com/v1.0/users'


client = CosmosClient(ENDPOINT, KEY)
database = client.create_database_if_not_exists(id='RestaurantDatabase')
restaurant_container = database.create_container_if_not_exists(
    id='RestaurantContainer',
    partition_key=('/style',),
    offer_throughput=400
)


request_log_container = database.create_container_if_not_exists(
    id='RequestLogContainer',
    partition_key=('/endpoint',),
    offer_throughput=400
)

# Define allowed roles for adding restaurants and viewing requests
ALLOWED_ROLES_RESTAURANT_CREATOR = ['RestaurantCreator']
ALLOWED_ROLES_REQUEST_VIEWER = ['RequestViewer']
ROLE_ID_RESTAURANT_CREATOR = os.environ['AZURE_ROLE_ID_RESTAURANT_CREATOR'] 
ROLE_ID_REQUEST_VIEWER = os.environ['AZURE_ROLE_ID_REQUEST_VIEWER']

def create_user(user_data):
    app.logger.info(f"Creating user: {user_data}")
    
    # Acquire token
    token = acquire_token()
    headers = {'Authorization': 'Bearer ' + token['access_token'], 'Content-Type': 'application/json'}
    
    # Create user
    response = requests.post(USERS_API_URL, headers=headers, json=user_data)
    response.raise_for_status()

    if 'RestaurantCreator' in user_data['roles']:
        assign_role(user_data["userPrincipalName"], ROLE_ID_RESTAURANT_CREATOR)
    if 'RequestLogViewer' in user_data['roles']:
        assign_role(user_data["userPrincipalName"], ROLE_ID_REQUEST_VIEWER)
    
    app.logger.info(f"User created successfully: {response.json()}")
    return response.json()


def create_users(user_data):
    users_file_path = os.path.join(os.path.dirname(__file__), 'users.json')
    with open(users_file_path, 'r') as file:
        users_data = json.load(file)
    
    created_users = []
    
    for user_data in users_data:
        try:
            user = create_user(user_data)
            created_users.append(user)
        except Exception as e:
            app.logger.error(f"Error creating user: {str(e)}")

def assign_role(user_id, role_id):
    app.logger.info(f"Assigning role {role_id} to user {user_id}")
    
    token = acquire_token()
    headers = {'Authorization': 'Bearer ' + token['access_token'], 'Content-Type': 'application/json'}
    
    url = f'{USERS_API_URL}/{user_id}/appRoleAssignments'
    data = {
        'principalId': user_id,
        'resourceId': role_id
    }
    
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    
    app.logger.info(f"Role assigned successfully: {response.json()}")


def setup():
    created_users = configure_ad_users()
    app.logger.info(f"Azure AD users configured at startup: {created_users}")

def acquire_token():
    from msal import ConfidentialClientApplication
    cca = ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY_URL,
        client_credential=CLIENT_SECRET
    )
    
    result = cca.acquire_token_for_client(scopes=SCOPE)
    return result

def configure_ad_users():
    users_file_path = os.path.join(os.path.dirname(__file__), 'users.json')
    with open(users_file_path, 'r') as file:
        users_data = json.load(file)
    
    created_users = []
    
    for user_data in users_data:
        try:
            user = create_user(user_data)
            created_users.append(user)
        except Exception as e:
            app.logger.error(f"Error creating user: {str(e)}")
    
    return created_users

@app.before_first_request
def setup():
    created_users = configure_ad_users()
    app.logger.info(f"Azure AD users configured at startup: {created_users}")

@app.route('/')
def index():
    return 'Flask Application'

@app.errorhandler(400)
def bad_request_error(error):
    return jsonify({"error": "Bad request"}), 400

@app.errorhandler(Exception)
def internal_server_error(error):
    app.logger.error('Internal Server Error: %s', error)
    return jsonify({"error": "Internal server error"}), 500

@app.route('/restaurants', methods=['POST'])
def create_restaurant():
    access_token = request.headers.get('Authorization')
    if not is_authorized(access_token, ALLOWED_ROLES_RESTAURANT_CREATOR):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    if not all(key in data for key in ('name', 'style', 'address', 'openHour', 'closeHour', 'vegetarian')):
        return jsonify({"error": "Incomplete data"}), 400

    item = {
        'name': data['name'],
        'style': data['style'],
        'address': data['address'],
        'openHour': data['openHour'],
        'closeHour': data['closeHour'],
        'vegetarian': data['vegetarian']
    }
    restaurant_container.create_item(body=item)
    return jsonify({"message": "Restaurant created successfully"}), 201

@app.route('/recommendations', methods=['GET'])
def get_recommendations():
    query_params = request.args.get('q')
    if not query_params:
        return jsonify({"error": "Query parameters not provided"}), 400

    criteria = parse_criteria(query_params)
    if not criteria:
        return jsonify({"error": "Invalid query parameters"}), 400

    query = "SELECT * FROM c WHERE"
    filters = []
    for key, value in criteria.items():
        filters.append(f" c.{key} = '{value}'")
    query += " AND".join(filters)

    results = list(restaurant_container.query_items(query, enable_cross_partition_query=True))
    if not results:
        return jsonify({"error": "No restaurants found matching the criteria"}), 404

    recommendations = []
    for item in results:
        recommendation = {
            'name': item['name'],
            'style': item['style'],
            'address': item['address'],
            'openHour': item['openHour'],
            'closeHour': item['closeHour'],
            'vegetarian': item['vegetarian']
        }
        recommendations.append(recommendation)

    log_request('/recommendations', request.args, recommendations)
    return jsonify({"restaurantRecommendations": recommendations})

@app.route('/requests', methods=['GET'])
def get_requests():
    access_token = request.headers.get('Authorization')
    if not is_authorized(access_token, ALLOWED_ROLES_REQUEST_VIEWER):
        return jsonify({"error": "Unauthorized"}), 403

    query = "SELECT * FROM c"
    results = list(request_log_container.query_items(query, enable_cross_partition_query=True))
    if not results:
        return jsonify({"error": "No requests found"}), 404

    requests = []
    for item in results:
        request_data = {
            'endpoint': item['endpoint'],
            'request': item['request'],
            'response': item['response'],
            'timestamp': item['timestamp']
        }
        requests.append(request_data)

    return jsonify({"requests": requests})

def log_request(endpoint, request_args, response):
    item = {
        'endpoint': endpoint,
        'request': request_args,
        'response': response,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }
    request_log_container.create_item(body=item)

def parse_criteria(query_string):
    criteria = {}
    
    options_mapping = {
        "glutenfree": "glutenFree",
        "vegetarian": "vegetarian",
        "vegan": "vegan",
        "dairyfree": "dairyFree"
    }
    
    food_styles_mapping = {
        "mexican": "Mexican",
        "italian": "Italian",
        "mediterranean": "Mediterranean",
        "chinese": "Chinese"
    }
    

    query_words = query_string.lower().split()

    for i, word in enumerate(query_words):
        if word in options_mapping:
            criteria[options_mapping[word]] = "true"
        elif word in food_styles_mapping:
            criteria["style"] = food_styles_mapping[word]
        elif word == "delivery":
            criteria["delivery"] = "true"
        elif word == "open":
            if i + 1 < len(query_words):
                open_hour = query_words[i + 1]
                if ":" in open_hour:
                    criteria["openHour"] = open_hour
        elif word == "close":
            if i + 1 < len(query_words):
                close_hour = query_words[i + 1]
                if ":" in close_hour:
                    criteria["closeHour"] = close_hour
        elif "street" in word or "avenue" in word or "boulevard" in word:
            address = " ".join(query_words[i:])
            criteria["address"] = address

    return criteria

def is_authorized(access_token, allowed_roles):
    cca = ConfidentialClientApplication(CLIENT_ID, authority=f'https://login.microsoftonline.com/{TENANT_ID}', client_credential=CLIENT_SECRET)
    result = cca.acquire_token_on_behalf_of(SCOPE, {'access_token': access_token})
    if 'access_token' in result:
        roles = result['id_token_claims'].get('roles', [])
        return any(role in allowed_roles for role in roles)
    return False

if __name__ == '__main__':
    app.run(debug=True)
