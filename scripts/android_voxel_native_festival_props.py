#!/usr/bin/env python3
"""Preserve small native festival BG sprites as upright 3D decorations.

Many Minish Cap flags, balloons and flower pots are painted on the top GBA
background rather than occupying OAM slots. Making every passable top BG
horizontal turns these into stripes across the grass/roofs. Identify only
SMALL colorful isolated top-BG components; stand their original alpha-tested
16px tiles vertically without adding physics or forcing an entire map layer
up. Larger continuous paving, plaza, carpets and buildings remain floor/roof.
"""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"upstream/tmc/port/port_voxel.cpp"
s=p.read_text(encoding="utf-8")
def patch(old,new):
    global s
    c=s.count(old)
    if c!=1: raise SystemExit(f"native festival art expected 1 anchor, got {c}: {old[:120]!r}")
    s=s.replace(old,new,1)

patch(
    """    /* ---- pass 1: classify columns into floor / prop / trunk / box runs and""",
    """    /* A part of the Hyrule town decorations is native BG art, NOT an OAM
     * entity. Classify tiny isolated, strongly coloured partial top layers
     * into actual two-sided sprite cards. These preserve their exact native
     * texels and transparency at all tilted camera pitches. */
    static Uint8 decorFeet[64 * 64]; /* 0=ordinary BG, y+1=object feet row */
    static Uint8 decorEligible[64 * 64], decorSeen[64 * 64];
    std::memset(decorFeet, 0, sizeof(decorFeet));
    std::memset(decorEligible, 0, sizeof(decorEligible));
    std::memset(decorSeen, 0, sizeof(decorSeen));
    if (outdoors && hasTop) {
        for (int y = 0; y < H; ++y)
            for (int x = 0; x < W; ++x) {
                const int t = y * 64 + x;
                if (Geom(x,y) || Cover(x,y) != 1 ||
                    SinkDepth(x,y) != 0.0f ||
                    gMapBottom.collisionData[t] == 0x0f ||
                    BridgeDeck(x,y) ||
                    TileOverride(t) == PORT_VOXEL_SHAPE_PROP)
                    continue;
                int painted=0, accented=0;
                for (int py=0;py<16;++py)
                    for (int px=0;px<16;++px) {
                        int pi=TopIndex(x,y,px,py,tChar,t8!=0);
                        if (pi<0) continue;
                        ++painted;
                        int c=gBgPltt[pi], r=c&31, g=(c>>5)&31, b=(c>>10)&31;
                        if (r>g+5 || b>g+5)
                            ++accented;
                    }
                // A path's broad neutral/tan surface must never stand up.
                if (painted>=12 && painted<=198 && accented>=6)
                    decorEligible[t]=1;
            }
        int queue[64*64];
        for (int y=0;y<H;++y)
            for (int x=0;x<W;++x) {
                const int start=y*64+x;
                if (!decorEligible[start] || decorSeen[start]) continue;
                int head=0, tail=0, minX=x,maxX=x,minY=y,maxY=y;
                queue[tail++]=start;
                decorSeen[start]=1;
                while (head<tail) {
                    const int t=queue[head++], cx=t%64, cy=t/64;
                    minX=std::min(minX,cx); maxX=std::max(maxX,cx);
                    minY=std::min(minY,cy); maxY=std::max(maxY,cy);
                    const int nx[4]={cx-1,cx+1,cx,cx};
                    const int ny[4]={cy,cy,cy-1,cy+1};
                    for (int i=0;i<4;++i) {
                        if (!inRoom(nx[i],ny[i])) continue;
                        const int ti=ny[i]*64+nx[i];
                        if (decorEligible[ti] && !decorSeen[ti]) {
                            decorSeen[ti]=1; queue[tail++]=ti;
                        }
                    }
                }
                // Only isolated individual stalls/bouquets/flags, not a
                // contiguous garden path, wall or multi-tile roof.
                if (tail <= 10 && maxX-minX < 4 && maxY-minY < 4)
                    for (int i=0;i<tail;++i)
                        decorFeet[queue[i]]=(Uint8)(maxY+1);
            }
    }

    /* ---- pass 1: classify columns into floor / prop / trunk / box runs and""")

start=s.index("    /* ---- pass 2: draw ---- */")
end=s.index("    for (const Run& rn : runs)",start)
portion=s[start:end]
if portion.count("if (Cover(x, y)) {") != 1:
    raise SystemExit(f"pass2 floor top anchor count {portion.count('if (Cover(x, y)) {')}")
portion=portion.replace("if (Cover(x, y)) {", "if (Cover(x, y) && decorFeet[t] == 0) {",1)
s=s[:start]+portion+s[end:]

patch(
    """    sMapVertCount = n;
    sBuildShapes = nullptr;""",
    """    /* 3D festival BG decorations: native top-background pixel art stands
     * at its group's foot row. This inverts the 2D oblique projection:
     * original screen Y = footZ - artHeight. No opaque box, no new collision,
     * and alpha 0 is discarded by the existing native BG shader. */
    for (int y=0;y<H;++y)
        for (int x=0;x<W;++x) {
            const int t=y*64+x;
            if (!decorFeet[t] || kind[t] != 0)
                continue;
            const float z=(float)decorFeet[t]*16.0f + 0.35f;
            const float hi=(float)(decorFeet[t]-y)*16.0f;
            const float lo=hi-16.0f;
            const float left=x*16.0f, right=left+16.0f;
            const float c[4][3]={
                {left,hi,z},{right,hi,z},
                {left,lo,z},{right,lo,z}};
            Quad(sMapVerts,kMaxMapVerts,n,c,
                 left,y*16.0f,right,y*16.0f+16.0f,
                 0,128u,tChar,t8);
        }
    sMapVertCount = n;
    sBuildShapes = nullptr;""")
p.write_text(s,encoding="utf-8")
print("Small colorful isolated top-BG decorations now stand as native transparent sprite cards")
