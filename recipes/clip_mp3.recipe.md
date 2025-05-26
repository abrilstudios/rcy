# MP3 Clipping Recipe

This recipe demonstrates how to extract a specific time segment from an MP3 file and convert it to WAV format using the RCY toolset.

## Prerequisites

- The `mp3extract` utility in the `bin/` directory
- An MP3 file to extract from

## Steps

1. **Identify the source MP3 file**

   The source file is located at `mp3/conga.mp3` in the project directory.

2. **Determine the time range to extract**

   For this recipe, we extract a 10-second segment from 2:55 to 3:05.

3. **Execute the extraction command**

   ```bash
   bin/mp3extract mp3/conga.mp3 2:55 3:05 --outfile=wav/conga_extract.wav --samplerate=44100
   ```

   Parameters explained:
   - First argument: Source MP3 file path
   - Second argument: Start time (2:55)
   - Third argument: End time (3:05)
   - `--outfile`: Path where the extracted WAV file will be saved
   - `--samplerate`: Sample rate for the output file (44100 Hz)

4. **Verify the extraction**

   The output file is created at `wav/conga_extract.wav` with the following properties:
   - Format: WAV
   - Sample rate: 44100 Hz
   - Bit depth: 16-bit
   - Channels: 2 (stereo)
   - Duration: 10 seconds
   - Size: ~1.7 MB

## How It Works

The `mp3extract` utility is a bash script that utilizes `ffmpeg` to perform the actual extraction. It:

1. Validates the input file
2. Checks the duration of the source file
3. Uses ffmpeg to extract the specified time segment
4. Converts the segment to WAV format with the specified sample rate
5. Outputs the resulting file to the specified path

## Example Output

```
Input file duration: 276.216000 seconds
Extracting from ~/experimental/rcy/mp3/conga.mp3 (2:55 to 3:05) to ~/experimental/rcy/wav/conga_extract.wav at 44100Hz
Extraction complete: ~/experimental/rcy/wav/conga_extract.wav
```

The extracted segment can now be loaded into RCY for further processing.