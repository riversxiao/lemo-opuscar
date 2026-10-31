import React from "react";
import { CalculateMetadataFunction, Composition } from "remotion";
import { Infographic } from "./Infographic";
import { loadFonts } from "./fonts";
import type { InfographicProps } from "./types";
import sample from "./sample-props.json";

loadFonts();

const FPS = 24;

// Duration comes from the props (plan_to_props.py); the frame size is fixed per composition,
// and props made for the other aspect are refused so a 9:16 plan never renders letterboxed.
const metadata =
  (aspect: InfographicProps["aspect"]): CalculateMetadataFunction<InfographicProps> =>
  ({ props }) => {
    if (props.aspect !== aspect) {
      throw new Error(
        `props are ${props.aspect} but this composition is ${aspect}: render ${
          props.aspect === "9:16" ? "InfographicPortrait" : "Infographic"
        }`
      );
    }
    if (props.fps !== FPS) throw new Error(`props fps ${props.fps}, the template renders ${FPS}`);
    return { durationInFrames: props.durationInFrames };
  };

const landscape = { ...(sample as InfographicProps), aspect: "16:9", width: 1920, height: 1080 } as InfographicProps;
const portrait = { ...(sample as InfographicProps), aspect: "9:16", width: 1080, height: 1920 } as InfographicProps;

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Infographic"
      component={Infographic}
      width={1920}
      height={1080}
      fps={FPS}
      durationInFrames={landscape.durationInFrames}
      defaultProps={landscape}
      calculateMetadata={metadata("16:9")}
    />
    <Composition
      id="InfographicPortrait"
      component={Infographic}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={portrait.durationInFrames}
      defaultProps={portrait}
      calculateMetadata={metadata("9:16")}
    />
  </>
);
