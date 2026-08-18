"""
CANON — FROZEN PROFILES. Reproduce the peak renders pixel-for-pixel
(verified: FINAL_daisies diff 0.0000/255).
HONEY70_CANON : spherical-65 honey (daisies / bike / hot tub / wave / snoot)
SCOPE70_CANON : 2x anamorphic character on 65mm (coast)
Pipeline: honey_sr.unrender -> [profile]. Do not modify.
FILM3 branch is shelved until it matches these outputs on the canon set.
"""
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, gaussian_filter1d, map_coordinates
import emulsify2 as E
E.GAUGE_WIDTH_MM[65]=48.56

def HONEY70_CANON(rgb_lin, seed=0):
    l0 = rgb_lin.mean(-1); sat = rgb_lin.max(-1)-rgb_lin.min(-1)
    ref = (l0>0.45)&(l0<0.92)&(sat < 0.10*np.maximum(l0,1e-6)+0.04)
    if ref.sum()>300:
        avg = np.array([rgb_lin[...,c][ref].mean() for c in range(3)])
        gains = np.clip((avg.mean()/np.maximum(avg,1e-6))**0.8,0.80,1.25)
        warmbias = float(np.clip((avg[0]-avg[2])/max(avg.mean(),1e-6),-0.5,0.8))
    else: gains = np.ones(3); warmbias = 0.0
    timed = np.clip(rgb_lin*gains[None,None,:],0,None)
    wb = np.clip(1.0-warmbias*1.4,0.35,1.0)
    r,g,b = timed[...,0],timed[...,1],timed[...,2]
    greenness = np.clip((g-np.maximum(r,b))/np.maximum(g,1e-6),0,1)
    yellow = np.clip((np.minimum(r,g)-b)/np.maximum(g,1e-6),0,1)
    fol = gaussian_filter(np.clip(greenness*2.2,0,1)*np.clip(0.35+yellow,0,1),2.0)
    timed = timed.copy()
    timed[...,1]*=(1-0.22*fol); timed[...,0]*=(1-0.16*fol); timed[...,2]*=(1-0.04*fol)
    med = np.median(timed.mean(-1))
    ev = np.clip(np.log2(0.16/max(med,1e-4))*0.55,-0.4,1.2)+0.2
    lum = timed.mean(-1)
    hotl = np.maximum(lum-0.45,0)*1.8
    swell = gaussian_filter(hotl**1.5,26.0)*0.21 + gaussian_filter(hotl**1.5,7.0)*0.10
    lit = timed.copy()
    lit[...,0]+=swell*(0.55+0.45*wb); lit[...,1]+=swell*0.80
    lit[...,2]+=swell*(0.83-0.23*wb)
    st = E.Stock2(gauge_mm=65, iso=200, crystal_fine_um=0.5, crystal_coarse_um=1.3,
                  coarse_frac=0.28, film_mtf_um=5.0, hal_thresh=0.55,
                  hal_core=0.55, hal_tail=0.28, interimage=0.42, adjacency=0.45,
                  print_gamma=2.0)
    out = E.emulsify2(lit, st, exposure_ev=ev, seed=seed)
    l = out.mean(-1,keepdims=True)
    cream = np.array([1.0,0.968,0.915]); cream = 1.0-(1.0-cream)*wb
    t = np.clip((l-0.62)/0.38,0,1)**1.6
    out = out*(1-t*0.42)+t*0.42*(l*cream[None,None,:])
    out = out/(1.0+0.11*np.maximum(out-0.65,0))
    warmblack = 0.026+(np.array([0.030,0.024,0.019])-0.026)*wb
    s = np.clip(1-l*3.2,0,1)**1.4
    out = out*(1-s)+(out*0.70+warmblack[None,None,:]*0.30)*s
    rng = np.random.default_rng(seed+1)
    tooth = gaussian_filter(rng.normal(0,1,out.shape[:2]),0.6)
    amp = 0.011*(0.35+np.clip(l[...,0],0,1)*(1-np.clip(l[...,0],0,1))*2.6)
    out = np.clip(out+(tooth*amp)[...,None],0,1)
    hgt,wid = out.shape[:2]
    field = rng.normal(0,1,(6,8))
    field = np.array(Image.fromarray((field*127+128).astype(np.uint8)).resize((wid,hgt),Image.BICUBIC))/128.0-1.0
    yy,xx = np.mgrid[0:hgt,0:wid]
    r2 = ((xx-wid/2)/(wid/2))**2+((yy-hgt/2)/(hgt/2))**2
    return np.clip(out*(1.0+0.012*field-0.022*r2**1.5)[...,None],0,1)

def SCOPE70_CANON(rgb_scene, seed=0):
    """Character engine v2 + emulsify2 at 65mm in squeezed space (made the coast)."""
    light = rgb_scene
    H,W,_ = light.shape
    yy,xx = np.mgrid[0:H,0:W].astype(np.float64)
    cx,cy = W/2,H/2; nx,ny=(xx-cx)/(W/2),(yy-cy)/(H/2); r2=nx**2+ny**2
    scale = 1+0.007*r2-0.006*r2**2
    xs=cx+(xx-cx)*scale; ys=cy+(yy-cy)*scale
    light = np.stack([map_coordinates(light[...,c],[ys,xs],order=1,mode="nearest") for c in range(3)],-1)
    for c,mag in [(0,1.0005),(2,0.9995)]:
        xs=cx+(xx-cx)*mag; ys=cy+(yy-cy)*mag
        light[...,c]=map_coordinates(light[...,c],[ys,xs],order=1,mode="nearest")
    fx=np.abs(nx)
    field=gaussian_filter(np.clip(0.1+0.9*(fx**2.4)*(1+0.25*np.sin(fx*np.pi*1.5))+0.18*ny**2,0,1),40)
    w_mid=np.clip(field*2,0,1)*(1-np.clip((field-0.55)*2.2,0,1))
    w_edge=np.clip((field-0.55)*2.2,0,1); w_c=1-np.clip(field*2,0,1)
    loca={0:1.06,1:1.00,2:1.10}
    out=np.zeros_like(light)
    for c in range(3):
        L0=light[...,c]
        L1=gaussian_filter(L0,(0.6*loca[c],1.3*loca[c]))
        L2=gaussian_filter(L0,(1.2*loca[c],2.6*loca[c]))
        out[...,c]=L0*w_c+L1*w_mid+L2*w_edge
    light=out
    lum=light.mean(-1); hot=np.maximum(lum-1.9,0)
    if hot.max()>0:
        s=gaussian_filter1d(gaussian_filter1d(hot,W*0.10,axis=1),1.8,axis=0)
        light+=s[...,None]*np.array([0.85,0.96,1.10])[None,None,:]*0.10
    light=np.clip(light,0,4.8)
    hw=W//2
    sq=np.stack([np.array(Image.fromarray((np.clip(light[...,c],0,4.8)*4096
        ).astype(np.uint16)).resize((hw,H),Image.LANCZOS)) for c in range(3)],-1)/4096.0
    st = E.Stock2(gauge_mm=65, iso=200, crystal_fine_um=0.5, crystal_coarse_um=1.3,
                  coarse_frac=0.28, film_mtf_um=5.0, hal_thresh=0.9,
                  hal_core=0.5, hal_tail=0.26, interimage=0.42, adjacency=0.45,
                  print_gamma=2.0)
    med = np.median(sq.mean(-1))
    ev = np.clip(np.log2(0.16/max(med,1e-4))*0.55,-0.4,1.4)+0.2
    out = E.emulsify2(np.clip(sq,0,None),st,exposure_ev=ev,seed=seed)
    l = out.mean(-1,keepdims=True)
    cream = np.array([1.0,0.968,0.915])
    t2 = np.clip((l-0.62)/0.38,0,1)**1.6
    out = out*(1-t2*0.42)+t2*0.42*(l*cream[None,None,:])
    out = out/(1.0+0.11*np.maximum(out-0.65,0))
    warmblack = np.array([0.030,0.024,0.019])
    s = np.clip(1-l*3.2,0,1)**1.4
    out = out*(1-s)+(out*0.70+warmblack[None,None,:]*0.30)*s
    rng = np.random.default_rng(seed+1)
    n = rng.normal(0,1,out.shape[:2])
    tooth = gaussian_filter(n,0.55)-gaussian_filter(n,1.6); tooth/=max(tooth.std(),1e-6)
    amp = 0.011*(0.35+np.clip(l[...,0],0,1)*(1-np.clip(l[...,0],0,1))*2.6)
    out = np.clip(out+(tooth*amp)[...,None],0,1)
    out16 = (np.clip(out,0,1)*65535).astype(np.uint16)
    proj=np.stack([np.array(Image.fromarray(out16[...,c]).resize((W,H),Image.LANCZOS))
                   for c in range(3)],-1)/65535.0
    hgt,wid = proj.shape[:2]
    yy,xx = np.mgrid[0:hgt,0:wid]
    rx=((xx-wid/2)/(wid/2))**2; ry=((yy-hgt/2)/(hgt/2))**2
    return np.clip(proj*(1.0-0.035*(rx*1.25+ry*0.6)**1.4)[...,None],0,1)
