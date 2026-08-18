
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
import emulsify2 as E
E.GAUGE_WIDTH_MM[65]=48.56

def unrender(arr_srgb):
    lin = E.srgb_to_linear(arr_srgb)
    L = lin.mean(-1,keepdims=True)
    t = 0.80
    over = np.clip((L-t)/(1-t),0,1)
    gain = 1.0 + 3.0*over**2.0
    lin = lin*gain
    L = lin.mean(-1,keepdims=True)
    m = np.clip(1-(L-0.6)/0.2,0,1)
    Ls = 0.18*np.power(np.maximum(L,1e-6)/0.18,0.90)
    lin = lin*((Ls/np.maximum(L,1e-6))*m + (1-m))
    L = lin.mean(-1,keepdims=True)
    lin = lin*(L/(L+0.012))
    return np.clip(lin,0,4.5)

def HONEY70_SR(rgb_scene, seed=0):
    proxy = np.clip(rgb_scene,0,1)
    l0 = proxy.mean(-1); sat0 = proxy.max(-1)-proxy.min(-1)
    ref = (l0>0.45)&(l0<0.92)&(sat0 < 0.10*np.maximum(l0,1e-6)+0.04)
    if ref.sum()>300:
        avg = np.array([proxy[...,c][ref].mean() for c in range(3)])
        gains = np.clip((avg.mean()/np.maximum(avg,1e-6))**0.8,0.80,1.25)
        warmbias = float(np.clip((avg[0]-avg[2])/max(avg.mean(),1e-6),-0.5,0.8))
    else: gains = np.ones(3); warmbias=0.0
    light = np.clip(rgb_scene*gains[None,None,:],0,None)
    wb = np.clip(1.0-warmbias*1.4,0.35,1.0)
    r,g,b = light[...,0],light[...,1],light[...,2]
    mx = np.maximum(light.max(-1),1e-6)
    greenness = np.clip((g-np.maximum(r,b))/mx,0,1)
    yellow = np.clip((np.minimum(r,g)-b)/mx,0,1)
    fol = gaussian_filter(np.clip(greenness*2.2,0,1)*np.clip(0.35+yellow,0,1),2.0)
    light = light.copy()
    light[...,1]*=(1-0.22*fol); light[...,0]*=(1-0.16*fol); light[...,2]*=(1-0.04*fol)
    med = np.median(light.mean(-1))
    ev = np.clip(np.log2(0.16/max(med,1e-4))*0.55,-0.4,1.4)+0.2
    lum = light.mean(-1)
    hot = np.tanh(np.maximum(lum-0.75,0)*0.55)
    swell = gaussian_filter(hot,26.0)*0.30 + gaussian_filter(hot,7.0)*0.14
    light[...,0]+=swell*(0.55+0.45*wb); light[...,1]+=swell*0.80
    light[...,2]+=swell*(0.83-0.23*wb)
    veil = gaussian_filter(hot, light.shape[1]/20.0)*0.10
    light = light + veil[...,None]*np.array([1.0,0.94,0.82])[None,None,:]*0.35
    st = E.Stock2(gauge_mm=65, iso=200, crystal_fine_um=0.5, crystal_coarse_um=1.3,
                  coarse_frac=0.28, film_mtf_um=5.0, hal_thresh=0.9,
                  hal_core=0.50, hal_tail=0.26, interimage=0.42, adjacency=0.45,
                  print_gamma=2.0)
    out = E.emulsify2(light, st, exposure_ev=ev, seed=seed)
    l = out.mean(-1,keepdims=True)
    R,G,B = out[...,0],out[...,1],out[...,2]
    mx2 = np.maximum(out.max(-1),1e-6); sat = out.max(-1)-out.min(-1)
    redness = np.clip((R-np.maximum(G,B))/mx2,0,1)*np.clip(sat*3,0,1)
    blueness = np.clip((B-np.maximum(R,G))/mx2,0,1)*np.clip(sat*3,0,1)
    yellown = np.clip((np.minimum(R,G)-B)/mx2,0,1)*np.clip(sat*3,0,1)
    out = np.clip(out*(1.0-0.05*redness-0.06*blueness+0.035*yellown)[...,None],0,1)
    skin = np.clip((R-B)/mx2,0,1)*np.clip((G-B)/mx2,0,1)
    skin = skin*np.clip(1-np.abs(l[...,0]-0.45)*2.2,0,1)
    skin = gaussian_filter(np.clip(skin*2.2-0.25,0,1),3.0)
    tr = np.array([1.0,0.80,0.62]); L2 = out.mean(-1,keepdims=True)
    out = out*(1-0.16*skin[...,None]) + np.clip(L2*3*tr[None,None,:]/tr.sum(),0,1)*(0.16*skin[...,None])
    Lp = out.mean(-1); Lb = gaussian_filter(Lp,out.shape[1]/16.0)
    pop = np.clip(1.0+0.07*(Lp-Lb)/np.maximum(Lp,0.06),0.90,1.10)
    guard = np.clip(1-(Lp-0.75)*4,0,1)*np.clip(Lp*8,0,1)
    out = np.clip(out*(1+(pop-1)*guard)[...,None],0,1)
    l = out.mean(-1,keepdims=True)
    cream = np.array([1.0,0.968,0.915]); cream = 1.0-(1.0-cream)*wb
    t2 = np.clip((l-0.62)/0.38,0,1)**1.6
    warmhold = gaussian_filter(np.clip(((out[...,0]-out[...,2])/np.maximum(out.max(-1),1e-6))*1.6,0,1),3)[...,None]
    t2 = t2*(1-0.5*warmhold)
    out = out*(1-t2*0.42)+t2*0.42*(l*cream[None,None,:])
    out = out/(1.0+0.11*np.maximum(out-0.65,0))
    warmblack = 0.026+(np.array([0.030,0.024,0.019])-0.026)*wb
    s = np.clip(1-l*3.2,0,1)**1.4
    out = out*(1-s)+(out*0.70+warmblack[None,None,:]*0.30)*s
    rng = np.random.default_rng(seed+1)
    n = rng.normal(0,1,out.shape[:2])
    tooth = gaussian_filter(n,0.55)-gaussian_filter(n,1.6)
    tooth = tooth/max(tooth.std(),1e-6)
    amp = 0.012*(0.35+np.clip(l[...,0],0,1)*(1-np.clip(l[...,0],0,1))*2.6)
    out = np.clip(out+(tooth*amp)[...,None],0,1)
    hgt,wid = out.shape[:2]
    field = rng.normal(0,1,(6,8))
    field = np.array(Image.fromarray((field*127+128).astype(np.uint8)).resize((wid,hgt),Image.BICUBIC))/128.0-1.0
    yy,xx = np.mgrid[0:hgt,0:wid]
    r2 = ((xx-wid/2)/(wid/2))**2+((yy-hgt/2)/(hgt/2))**2
    return np.clip(out*(1.0+0.012*field-0.022*r2**1.5)[...,None],0,1)
