import boto3
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

def test_spaces_connection():
    try:
        print("\nInitializing Spaces client...")
        print(f"Endpoint: https://{os.getenv('DO_SPACES_ENDPOINT')}")
        print(f"Region: {os.getenv('DO_SPACES_REGION')}")
        print(f"Space Name: {os.getenv('DO_SPACE_NAME')}")
        
        # Initialize the Spaces client
        session = boto3.session.Session()
        client = session.client('s3',
            region_name=os.getenv('DO_SPACES_REGION'),
            endpoint_url=f"https://{os.getenv('DO_SPACES_ENDPOINT')}",
            aws_access_key_id=os.getenv('DO_SPACES_KEY'),
            aws_secret_access_key=os.getenv('DO_SPACES_SECRET')
        )

        # Create a test file
        test_content = f"Test file created at {datetime.now().isoformat()}"
        test_filename = "test.txt"
        with open(test_filename, "w") as f:
            f.write(test_content)

        print("\n1. Created test file locally")
        print(f"   Content: {test_content}")

        # Upload the file
        space_name = os.getenv('DO_SPACE_NAME')
        space_path = f"test/{test_filename}"
        
        print(f"\n2. Uploading file to {space_name}/{space_path}")
        with open(test_filename, 'rb') as f:
            client.upload_fileobj(
                f,
                space_name,
                space_path,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': 'text/plain'
                }
            )
        print("   Upload successful")

        # Verify the file exists via CDN
        cdn_url = f"{os.getenv('CDN_BASE_URL')}/test/{test_filename}"
        print(f"\n3. Verifying file via CDN")
        print(f"   URL: {cdn_url}")
        
        response = requests.get(cdn_url)
        
        if response.status_code == 200:
            print("   Successfully retrieved file from CDN")
            print(f"   Content: {response.text}")
        else:
            print(f"   Failed to retrieve file from CDN: {response.status_code}")
            print(f"   Response: {response.text}")

        # Clean up
        print("\n4. Cleaning up")
        client.delete_object(Bucket=space_name, Key=space_path)
        os.remove(test_filename)
        print("   Removed test files")

        return True

    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing Digital Ocean Spaces connection...")
    success = test_spaces_connection()
    print(f"\nTest {'succeeded' if success else 'failed'}") 