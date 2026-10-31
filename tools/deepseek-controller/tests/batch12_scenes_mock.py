"""finance-v003 batch-12 scenes (no network): CCP / CIP / MBS / prepayment / CDS"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import viz_pick as vp

ok_n = 0
def ok(cond, msg):
    global ok_n
    if not cond:
        print('FAIL:', msg); sys.exit(1)
    ok_n += 1

DRAFTS = Path('/workspace/films/dialogue-drafts')
WANT = {
    'ccp-v001': ['ccp_handshake','ccp_title','ccp_sellers','ccp_buyers','ccp_worry','ccp_star','ccp_net','ccp_margin','ccp_dfund','ccp_2008','ccp_clear','ccp_focus','ccp_solid'],
    'covered-interest-parity-v001': ['cip_fork','cip_title','cip_home','cip_102','cip_fx','cip_105','cip_lock','cip_equal','cip_convert','cip_weaker','cip_offset','cip_gap','cip_cost','cip_discount'],
    'mbs-v001': ['mbs_pack','mbs_title','mbs_pool','mbs_slice','mbs_flow','mbs_holders','mbs_relend','mbs_spread','mbs_two','mbs_default','mbs_prepay','mbs_2008','mbs_shift'],
    'prepayment-risk-v001': ['pp_coin','pp_title','pp_6pct','pp_4pct','pp_refi','pp_rush','pp_back','pp_reinvest','pp_curves','pp_convex','pp_end'],
    'cds-v001': ['cds_shield','cds_title','cds_fee','cds_crack','cds_payout','cds_unlike','cds_naked','cds_empty','cds_cpty','cds_pile','cds_crush','cds_bail','cds_ask'],
}
B12 = []
for fid, want in WANT.items():
    L = json.loads((DRAFTS / f'{fid}.lines.json').read_text())
    got = [vp.pick_scene(l['visual']) for l in L]
    ok(got == want and len(set(got)) == len(want), f'{fid}: {got} → want {want}')
    B12.extend(want)

ok(len(B12) == 64 and len(set(B12)) == 64, '64 batch-12 scenes, unique')
sj = (ROOT.parent.parent / 'styles/pictogram-motion/versions/finance-v003/scenes.js').read_text()
ok(all(f'VIZ.{s} =' in sj and re.search(rf"\b{s}: '", sj) for s in B12), 'every batch-12 scene drawn + palette')
b12 = sj[sj.index('finance-v003 scene library, batch 12'):sj.index('finance-v003 scene library, batch 11')]
code = b12
code2=re.sub(r'违约基金','',code)
ok(not re.search(r'基金|ETF|筹码|赌|骰|扑克|轮盘|赌场|彩票|中奖|K线|值得买|稳赚|机会大|小钱(?!币)|撬|√|Σ', code2), 'batch-12 scene text: no funds/gambling/K-lines/buy-signals')
ok("'远期贴水'" in code and "'负凸性'" in code and "'对手方风险'" in code, 'key labels present')
print(f'{ok_n} ok')
