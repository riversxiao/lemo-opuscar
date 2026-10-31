// Remotion CLI defaults for the WordFilm infographic template.
// render.sh passes everything that differs per film (props, codec, browser) on the command line.
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
