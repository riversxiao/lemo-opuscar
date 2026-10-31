// styles/swiss-motion/demo/film.js 9:16 statement fit without a browser or the demo fonts: a stub
// canvas measures a CJK character as 1 em and other characters as about half an em. Checks that
// Chinese copy (no spaces) breaks inside the run and stays within the 936 px measure on at most two
// lines, that English copy keeps its size and measure, and that landscape never wraps.
// Prints one line per check; exits 1 on any failure.
import { setFrame, fitLine, layBig, breakPieces } from '../../../styles/swiss-motion/demo/film.js';

let failed = 0;
const check = (cond, msg) => { console.log((cond ? 'ok ' : 'not ok ') + msg); if (!cond) failed++; };
const CJK = /[\u2E80-\u9FFF\uFF00-\uFFEF]/;
const g = {
  size: 10, letterSpacing: '0px',
  set font(f) { this.size = parseFloat(f.split(' ')[1]); },
  measureText(s) { return { width: [...s].reduce((w, c) => w + this.size * (CJK.test(c) ? 1 : c === ' ' ? .28 : .56), 0) }; },
};
const fit = (big, small = '') => {
  const L = { id: 'x', big, small, soft: false }, F = fitLine(g, L, 76);
  g.font = `700 ${F.big}px Archivo`;
  const runs = layBig(g, big.split(' '), 0, F.measure).runs;
  return { F, runs, right: Math.max(...runs.map(r => r.x + g.measureText(r.s).width)), lines: new Set(runs.map(r => r.line)).size };
};

check(JSON.stringify(breakPieces('grid.')) === '["grid."]', 'a Latin word stays whole');
check(breakPieces('不是把鸡蛋随便一撒。').at(-1) === '撒。', 'closing punctuation stays with the character before it');
check(JSON.stringify(breakPieces('（真的）')) === '["（真","的）"]', 'no break after opening or before closing brackets');
check(JSON.stringify(breakPieces('AI时代')) === '["AI","时","代"]', 'Latin next to CJK may break, Latin inside stays whole');

setFrame(1080, 1920);
let r = fit('Build a grid.', 'Rule one.');
check(r.F.big === 76 && r.F.lines === 1 && r.F.measure === 936, `English statement keeps 76 px, one line, 936 measure (${r.F.big}, ${r.F.lines}, ${r.F.measure})`);
r = fit('A different song every time.');
check(r.F.big === 76 && r.F.lines === 2 && r.F.measure === 936, `long English statement: two lines at 76 px, measure kept (${r.F.big}, ${r.F.lines}, ${r.F.measure})`);

r = fit('不是把鸡蛋随便一撒而是网格。');   // 14 hanzi: wider than the measure at 76 px
check(r.F.big === 76 && r.lines === 2 && r.right <= 936, `14 hanzi: two lines at 76 px within the measure (right edge ${r.right})`);
const second = r.runs.filter(x => x.line === 1).map(x => x.s).join('');
check([...second].length >= 6, `14 hanzi: the second line is balanced, not an orphan ("${second}")`);

r = fit('先画网格，不是把鸡蛋随便一撒，而是让每一个元素都有自己的位置。');   // 31 hanzi
check(r.F.lines === 2 && r.lines === 2 && r.right <= 936 && r.F.big >= 36, `31 hanzi: two lines at ${r.F.big} px within the measure (right edge ${r.right})`);

r = fit('所有东西都对齐到同一条线上，包括数字、标点和图片的边缘，一个都不例外，这样整页才会安静下来，再多写一点点。');
check(r.F.big === 36 && r.F.lines === 3 && r.right <= 936, `57 hanzi: 36 px floor, ${r.F.lines} lines reported (warns), still within the measure (right edge ${r.right})`);

r = fit('每一次都是一首完全不一样的歌，Swiss Style 2024 版。');
check(r.lines <= 2 && r.right <= 936, `mixed Chinese and English: ${r.lines} lines within the measure at ${r.F.big} px`);

setFrame(1920, 1080);
r = fit('先画网格，不是把鸡蛋随便一撒，而是让每一个元素都有自己的位置。');
check(r.F.measure === Infinity && r.F.big === 76 && r.lines === 1, 'landscape: one line at 76 px, no measure');

process.exit(failed ? 1 : 0);
