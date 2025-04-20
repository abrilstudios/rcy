#!/bin/bash

# Script to import GitHub labels for the L1/L2 workflow
# Requires the GitHub CLI (gh) to be installed and authenticated

# Repository name - replace with your actual repository
REPO="abrilstudios/rcy"

echo "Creating L1/L2 workflow labels in repository $REPO..."

# Read the labels JSON file and create each label
cat github_labels.json | jq -c '.[]' | while read label; do
  name=$(echo $label | jq -r '.name')
  color=$(echo $label | jq -r '.color')
  description=$(echo $label | jq -r '.description')
  
  echo "Creating label: $name"
  gh label create "$name" --color "$color" --description "$description" --repo "$REPO" || gh label edit "$name" --color "$color" --description "$description" --repo "$REPO"
done

echo "Label setup complete."