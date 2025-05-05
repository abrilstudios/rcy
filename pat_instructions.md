# Creating a GitHub Personal Access Token

## Step-by-Step Instructions

1. Log in to GitHub as abrilstudios-claude1 at https://github.com/login

2. Go to Settings:
   - Click on your profile picture in the top-right corner
   - Select "Settings" from the dropdown menu

3. Navigate to Developer settings:
   - Scroll down to the bottom of the left sidebar
   - Click on "Developer settings" (the last option in the sidebar)

4. Access Personal access tokens:
   - In the left sidebar of Developer settings, you'll see:
   - Click on "Personal access tokens"
   - Choose either:
     - "Fine-grained tokens" (recommended, more granular permissions)
     - "Tokens (classic)" (older style with broader permissions)

5. Create a new token:
   - Click "Generate new token"
   - For fine-grained tokens: Click "Generate new token"
   - For classic tokens: Click "Generate new token (classic)"

6. Configure the token:
   - Name: "RCY Repository Access" (or any descriptive name)
   - Expiration: Choose an appropriate duration (30 days, 60 days, custom, etc.)
   - Permissions:
     - For classic tokens: Select "repo" (full control) and optionally "workflow"
     - For fine-grained tokens: Select access to specific repositories (abrilstudios/rcy) and set permissions for "Contents" to "Read and write"

7. Generate the token:
   - Scroll down and click "Generate token"

8. Copy the token immediately:
   - GitHub will show the token only once
   - Copy it to a secure, temporary location
   - You'll need this when pushing to GitHub

## Direct URLs

- Fine-grained tokens: https://github.com/settings/tokens?type=beta
- Classic tokens: https://github.com/settings/tokens

## Using the Token

When pushing to GitHub for the first time, you'll be prompted for credentials:
- Username: abrilstudios-claude1
- Password: [paste the token you copied]

macOS Keychain will store this for future use.