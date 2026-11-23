import {Config} from '@remotion/cli/config';

// Grafis dirender sebagai overlay transparan (ProRes 4444) lalu ditumpuk oleh vedit (FFmpeg).
Config.setVideoImageFormat('png');
Config.setOverwriteOutput(true);
Config.setConcurrency(null);
