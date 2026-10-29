// core/three/post.js sizing without a GPU: a stub renderer is enough for makePost to build
// its passes. Checks that the DOF/GTAO targets stay at w*ssaa x h*ssaa for any renderer
// pixel ratio (EffectComposer.addPass must not resize them), and that post.setSize
// re-targets them for a portrait frame. Prints one line per check; exits 1 on any failure.
import { makePost } from '../../../core/three/post.js';
import * as THREE from 'three';

let failed = 0;
const check = (cond, msg) => { console.log((cond ? 'ok ' : 'not ok ') + msg); if (!cond) failed++; };
const stub = (pr, w, h) => ({ getPixelRatio: () => pr, getSize: (v) => v.set(w, h) });
const size = (rt) => `${rt.width}x${rt.height}`;

for (const pr of [1, 2]) {
  const r = stub(pr, 1920, 1080);
  const post = makePost(r, new THREE.Scene(), new THREE.PerspectiveCamera(), 1920, 1080, { ssaa: 2, ao: true });
  const d = post.dof, res = d.gat.material.uniforms.res.value;
  check(size(d.rt) === '3840x2160', `pr${pr}: dof.rt ${size(d.rt)} == 3840x2160 after addPass`);
  check(size(d.rtC) === '3840x2160', `pr${pr}: dof.rtC ${size(d.rtC)} == 3840x2160`);
  check(res.x === 3840 && res.y === 2160, `pr${pr}: gather res ${res.x}x${res.y} == 3840x2160`);
  check(size(post.composer.renderTarget1) === '3840x2160', `pr${pr}: composer buffer ${size(post.composer.renderTarget1)} == dof.rt`);
  const bloomW0 = post.bloom.renderTargetsHorizontal[0].width;

  post.setSize(1080, 1920);
  check(size(d.rt) === '2160x3840', `pr${pr}: post.setSize(1080,1920) dof.rt ${size(d.rt)} == 2160x3840`);
  check(res.x === 2160 && res.y === 3840, `pr${pr}: gather res follows (${res.x}x${res.y})`);
  check(size(post.composer.renderTarget1) === '2160x3840', `pr${pr}: composer buffer ${size(post.composer.renderTarget1)} == dof.rt`);
  if (d.ao) check(d.ao.width === 2160 && d.ao.height === 3840, `pr${pr}: GTAO ${d.ao.width}x${d.ao.height} follows`);

  post.setSize(1920, 1080);
  check(size(d.rt) === '3840x2160' && size(post.composer.renderTarget1) === '3840x2160', `pr${pr}: back to 1920x1080 restores construction sizes`);
  check(post.bloom.renderTargetsHorizontal[0].width === bloomW0, `pr${pr}: bloom mip0 width back to construction value ${bloomW0}`);
}
process.exit(failed ? 1 : 0);
