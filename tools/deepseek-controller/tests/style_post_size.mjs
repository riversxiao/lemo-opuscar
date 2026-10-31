// styles/hd-2d/demo/post_ts.js and styles/lowpoly-island/demo/post.js sizing without a GPU (same stub renderer as
// three_post_size.mjs). At 1920x1080 ssaa 2 every target is 3840x2160, as before these copies learned setSize; post.setSize
// re-targets them for a portrait frame and back. Prints one line per check; exits 1 on any failure.
import * as THREE from 'three';
import { makePost as hd2d } from '../../../styles/hd-2d/demo/post_ts.js';
import { makePost as lowpoly } from '../../../styles/lowpoly-island/demo/post.js';

let failed = 0;
const check = (cond, msg) => { console.log((cond ? 'ok ' : 'not ok ') + msg); if (!cond) failed++; };
const stub = (pr, w, h) => ({ getPixelRatio: () => pr, getSize: (v) => v.set(w, h) });
const size = (rt) => `${rt.width}x${rt.height}`;
const vec = (v) => `${v.x}x${v.y}`;

// name, makePost, camera, the scene pass, [label, () => vec-like] pairs that must follow the size
const cases = [
  ['hd-2d', hd2d, () => new THREE.PerspectiveCamera(), (p) => p.dof, (p) => [['gather res', p.dof.gat.material.uniforms.res.value]], { ao: true }],
  ['lowpoly-island', lowpoly, () => new THREE.OrthographicCamera(), (p) => p.sp, (p) => [['comp res', p.comp.res.value], ['tilt res', p.tilt.res.value]], {}],
];
for (const [name, makePost, cam, pass, uni, extra] of cases) {
  const post = makePost(stub(1, 1920, 1080), new THREE.Scene(), cam(), 1920, 1080, { ssaa: 2, ...extra });
  const sp = pass(post);
  check(size(sp.rt) === '3840x2160', `${name}: scene target ${size(sp.rt)} == 3840x2160 at 1920x1080 ssaa 2`);
  check(size(post.composer.renderTarget1) === '3840x2160', `${name}: composer buffer ${size(post.composer.renderTarget1)} == 3840x2160`);
  for (const [l, v] of uni(post)) check(vec(v) === '3840x2160', `${name}: ${l} ${vec(v)} == 3840x2160`);
  if (sp.ao) check(sp.ao.width === 3840 && sp.ao.height === 2160, `${name}: GTAO ${sp.ao.width}x${sp.ao.height} == 3840x2160`);
  const bloom0 = post.bloom.renderTargetsHorizontal[0].width;
  check(typeof post.setSize === 'function', `${name}: post.setSize exists`);
  if (typeof post.setSize !== 'function') continue;
  post.setSize(1080, 1920);
  check(size(sp.rt) === '2160x3840', `${name}: setSize(1080,1920) scene target ${size(sp.rt)} == 2160x3840`);
  check(size(post.composer.renderTarget1) === '2160x3840', `${name}: composer buffer follows (${size(post.composer.renderTarget1)})`);
  for (const [l, v] of uni(post)) check(vec(v) === '2160x3840', `${name}: ${l} follows (${vec(v)})`);
  if (sp.ao) check(sp.ao.width === 2160 && sp.ao.height === 3840, `${name}: GTAO follows (${sp.ao.width}x${sp.ao.height})`);
  post.setSize(1920, 1080);
  check(size(sp.rt) === '3840x2160' && size(post.composer.renderTarget1) === '3840x2160', `${name}: back to 1920x1080 restores construction sizes`);
  check(post.bloom.renderTargetsHorizontal[0].width === bloom0, `${name}: bloom mip0 width back to ${bloom0}`);
}
process.exit(failed ? 1 : 0);
