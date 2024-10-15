#include <iostream>
#include <vector>
#include <cmath>
#include "time_stretch.hpp"

// Constants
constexpr double PI = 3.141592653589793238460;

// Function to apply crossfade between two grains
void apply_crossfade(std::vector<double>& output, const std::vector<double>& grain, int start, int fade_length) {
    for (int i = 0; i < fade_length; ++i) {
        double fade_factor = static_cast<double>(i) / fade_length;
        output[start + i] = output[start + i] * (1.0 - fade_factor) + grain[i] * fade_factor;
    }
}

// Grain-based time-stretching
std::vector<double> time_stretch_grains(const std::vector<double>& input, double stretch_factor, int grain_size, int overlap) {
    int num_grains = static_cast<int>((input.size() - grain_size) / (grain_size - overlap)) + 1;
    int output_size = static_cast<int>(input.size() * stretch_factor);
    std::vector<double> output(output_size, 0.0);
    int output_index = 0;
    int fade_length = overlap;

    for (int i = 0; i < num_grains; ++i) {
        // Extract the current grain
        int input_index = i * (grain_size - overlap);
        std::vector<double> grain(input.begin() + input_index, input.begin() + input_index + grain_size);

        // Compute where this grain should be placed in the stretched output
        int grain_output_start = static_cast<int>(output_index * stretch_factor);

        // Apply the grain to the output with overlap-add
        for (int j = 0; j < grain_size; ++j) {
            if (grain_output_start + j < output.size()) {
                output[grain_output_start + j] += grain[j];
            }
        }

        // Apply crossfade for smoothing
        if (i > 0 && grain_output_start - fade_length >= 0) {
            apply_crossfade(output, grain, grain_output_start - fade_length, fade_length);
        }

        // Move to the next grain position
        output_index += (grain_size - overlap);
    }

    return output;
}

// Example usage
int main() {
    // Test input signal (example sine wave)
    const int sample_rate = 44100;
    const double duration = 1.0;
    std::vector<double> input(sample_rate * duration);

    // Generate sine wave
    for (int i = 0; i < input.size(); ++i) {
        input[i] = sin(2 * PI * 440 * i / sample_rate);
    }

    // Time-stretch by 1.5x using grain-based approach
    double stretch_factor = 1.5;
    std::vector<double> stretched = time_stretch_grains(input, stretch_factor, 512, 128);

    // Output the stretched signal (for example, print the first 100 samples)
    for (size_t i = 0; i < std::min(stretched.size(), static_cast<size_t>(100)); ++i) {
        std::cout << stretched[i] << std::endl;
    }

    return 0;
}

