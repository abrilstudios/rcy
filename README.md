# RCY

**RCY** is a tool designed to process breakbeat loops, enabling users to slice and export them in the **SFZ** format for seamless integration with samplers like the **TAL-Sampler**.

<img width="800" alt="Screenshot 2024-10-05 at 10 33 44 AM" src="https://github.com/user-attachments/assets/53442622-ae80-4a2b-830b-75135060a79a">

## Features

- **Breakbeat Slicing**: Automatically detects transients in breakbeat loops and slices them into individual hits.
- **SFZ Export**: Generates SFZ files with mappings corresponding to the sliced samples, facilitating easy import into compatible samplers.
- **User-Friendly Interface**: Provides a straightforward interface for loading audio files, adjusting slice parameters, and exporting results.

## Requirements

- **Python 3.x**: Ensure Python is installed on your system.
- **Dependencies**: Install necessary Python packages using the provided `requirements.txt` file.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/tnn1t1s/rcy.git
   cd rcy
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Run python3 src/python/main.py**
2. **Load an Audio File**: Import your breakbeat loop into the application.
3. **Adjust Slicing Parameters**: Configure settings such as sensitivity to tailor the slicing process to your needs.
4. **Export as SFZ**: Save the sliced samples and generate an SFZ file for use in samplers like the TAL-Sampler.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your enhancements or bug fixes.

## License

This project is licensed under the [MIT License](LICENSE).
