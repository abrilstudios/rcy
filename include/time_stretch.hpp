#ifndef TIME_STRETCH_HPP
#define TIME_STRETCH_HPP

#include <vector>

// Function declarations
std::vector<double> time_stretch_grains(const std::vector<double>& input, double stretch_factor, int grain_size = 512, int overlap = 128);
void apply_crossfade(std::vector<double>& output, const std::vector<double>& grain, int start, int fade_length);

#endif // TIME_STRETCH_HPP

