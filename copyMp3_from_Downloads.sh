#!/bin/bash

# Define source and destination directories
src_dir="$HOME/Downloads"
dest_dir=./mp3/

# Create the destination directory if it doesn't exist
mkdir -p "$dest_dir"

# Loop through matching files
for file in "$src_dir"/ytmp3free.cc_*-youtubemp3free.org.mp3; do
    # Extract the base filename
    base_name=$(basename "$file")
    
    # Remove the prefix and suffix
    new_name="${base_name#ytmp3free.cc_}"
    new_name="${new_name%_youtubemp3free.org.mp3}.mp3"
    
    # Copy the file to the destination directory with the new name
    cp "$file" "$dest_dir/$new_name"
done

