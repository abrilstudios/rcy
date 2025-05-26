# Setting up GitHub Authentication for abrilstudios-claude1

## Option 1: Personal Access Token (Recommended)

1. Log in to GitHub as abrilstudios-claude1
2. Go to Settings → Developer settings → Personal access tokens → Fine-grained tokens (or Classic tokens)
3. Create a new token with appropriate permissions (repo scope needed for repository access)
4. Copy the generated token

Then configure git to use this token:

```bash
# This will prompt for username and password (use token as password)
git push

# Enter username: abrilstudios-claude1
# Enter password: [paste token here]
```

The credential helper (osxkeychain) will store this for future use.

## Option 2: SSH Keys

1. Generate an SSH key pair for this user:
```bash
ssh-keygen -t ed25519 -C "abrilstudios-claude1@proton.me" -f ~/.ssh/abrilstudios_claude1
```

2. Add the key to the SSH agent:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/abrilstudios_claude1
```

3. Add the public key to GitHub account:
   - Copy the public key: `cat ~/.ssh/abrilstudios_claude1.pub`
   - Go to GitHub Settings → SSH and GPG keys → New SSH key
   - Paste the key and save

4. Update the repository to use SSH:
```bash
git remote set-url origin git@github.com:abrilstudios/rcy.git
```

## Option 3: GitHub CLI

1. Install GitHub CLI if not already installed:
```bash
brew install gh
```

2. Authenticate with GitHub:
```bash
gh auth login
```
- Follow the prompts to authenticate
- Select GitHub.com
- Select HTTPS
- Enter username and password/token

3. Check authentication status:
```bash
gh auth status
```

## Using Different Credentials for Different Repositories

Create or edit `~/.gitconfig` to use different credentials for different repositories:

```
[includeIf "gitdir:~/experimental/rcy/"]
  path = ~/.gitconfig-abrilstudios

[includeIf "gitdir:/path/to/personal/repos/"]
  path = ~/.gitconfig-personal
```

Then create `~/.gitconfig-abrilstudios`:
```
[user]
  name = abrilstudios-claude1
  email = abrilstudios-claude1@proton.me
```

And `~/.gitconfig-personal`:
```
[user]
  name = David Palaitis
  email = david.j.palaitis@gmail.com
```