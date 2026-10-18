"""Build the ACS county rent burden analysis. Offline unless --refresh."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from zipfile import ZipFile
import importlib.metadata
import numpy as np
import pandas as pd
import geopandas as gpd
import os
import tempfile
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'aeds6400-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

POST = Path(__file__).resolve().parent
RAW = POST / 'data' / 'raw'
RESULTS = POST / 'results'
SOURCES = {
 'b25070_county.zip': 'https://www2.census.gov/programs-surveys/acs/replicate_estimates/2024/data/5-year/050/B25070.csv.zip',
 'b25070_state.zip': 'https://www2.census.gov/programs-surveys/acs/replicate_estimates/2024/data/5-year/040/B25070.csv.zip',
 'counties_2024.zip': 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip',
}
REP = [f'Var_Rep{i}' for i in range(1,81)]
COLS = ['ESTIMATE'] + REP

def digest(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def acquire(refresh):
 manifest_path = RAW / 'provenance.json'
 if refresh:
  import requests
  manifest=[]
  for name,url in SOURCES.items():
   response=requests.get(url,timeout=120);response.raise_for_status()
   path=RAW/name;path.write_bytes(response.content)
   with ZipFile(path) as z: assert z.testzip() is None
   manifest.append(dict(file=name,url=url,retrieved_utc=datetime.now(timezone.utc).isoformat(),sha256=digest(path),bytes=path.stat().st_size))
  manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
 else:
  if not manifest_path.exists(): raise FileNotFoundError('Missing provenance. Run once with --refresh.')
  manifest=json.loads(manifest_path.read_text())
  assert {r['file'] for r in manifest} == set(SOURCES)
  for r in manifest:
   assert r['url']==SOURCES[r['file']]
   assert digest(RAW/r['file'])==r['sha256'], f"Checksum mismatch: {r['file']}"


def read_vre(filename,prefix):
 with ZipFile(RAW/filename) as z:
  # Census CSV contains Latin-1 names for geographies outside Pennsylvania.
  df=pd.read_csv(z.open(z.namelist()[0]),encoding='latin1',dtype={'GEOID':str})
 df=df[df.GEOID.fillna('').str.startswith(prefix)].copy()
 assert not df.duplicated(['GEOID','ORDER']).any()
 df['ORDER']=df.ORDER.astype(int)
 assert np.isfinite(df[COLS].to_numpy()).all()
 assert (df[COLS]>=0).all().all()
 return df


def summarize(df):
 records=[];replicates={}
 for geoid,g in df.groupby('GEOID'):
  x=g.set_index('ORDER').sort_index()
  assert list(x.index)==list(range(1,12))
  values=x[COLS]
  assert np.allclose(values.loc[1],values.loc[2:11].sum())
  den=values.loc[2:10].sum().to_numpy()
  assert (den>0).all()
  numerator=values.loc[7:10].sum().to_numpy()
  severe=values.loc[10].to_numpy()
  pct=100*numerator/den;sev=100*severe/den
  moe=1.645*np.sqrt(4/80*np.sum((pct[1:]-pct[0])**2))
  sev_moe=1.645*np.sqrt(4/80*np.sum((sev[1:]-sev[0])**2))
  row=dict(geoid=geoid.split('US')[1],name=x.NAME.iloc[0].replace(' County, Pennsylvania',''),
   total_renter_households=int(values.loc[1,'ESTIMATE']),not_computed=int(values.loc[11,'ESTIMATE']),
   eligible_households=int(den[0]),burdened_households=int(numerator[0]),severe_households=int(severe[0]),
   burden_pct=float(pct[0]),moe90=float(moe),lower90=float(max(0,pct[0]-moe)),upper90=float(min(100,pct[0]+moe)),
   severe_pct=float(sev[0]),severe_moe90=float(sev_moe))
  assert 0<=row['severe_pct']<=row['burden_pct']<=100
  records.append(row);replicates[row['geoid']]=pct
 return pd.DataFrame(records),replicates


def style():
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titleweight':'bold','text.color':'#172f3c',
  'axes.labelcolor':'#172f3c','xtick.color':'#415562','ytick.color':'#172f3c','figure.facecolor':'#faf9f5','axes.facecolor':'#faf9f5',
  'savefig.facecolor':'#faf9f5','svg.fonttype':'none'})


def save(fig,name):
 for ext in ['png','svg']:
  fig.savefig(RESULTS/'figures'/f'{name}.{ext}',dpi=190,bbox_inches='tight',pad_inches=.22)
 plt.close(fig)


def draw_map(gdf):
 colors=['#e5f1ed','#b8d9d0','#78b5ac','#387f85','#174955']
 bounds=[0,40,45,50,55,100]
 fig,ax=plt.subplots(figsize=(11.6,7.4))
 fig.suptitle('Centre and Monroe stand out on the rent burden map',x=.045,y=.985,ha='left',fontsize=19,fontweight='bold')
 fig.text(.045,.925,'Share of renter households spending at least 30% of income on rent and utilities',fontsize=11.5)
 gdf.plot(column='burden_pct',cmap=ListedColormap(colors),norm=BoundaryNorm(bounds,5),edgecolor='#faf9f5',linewidth=.85,ax=ax)
 offsets={'Centre':(0,12),'Monroe':(24,14),'Lehigh':(-25,-8),'Delaware':(-56,-42),'Philadelphia':(35,-25),'Allegheny':(-5,-15)}
 for name,offset in offsets.items():
  row=gdf[gdf.name==name].iloc[0];point=row.geometry.representative_point()
  ax.plot(point.x,point.y,'o',ms=3.3,color='#a23b19',zorder=3)
  ax.annotate(name,xy=(point.x,point.y),xytext=offset,textcoords='offset points',ha='center',va='center',fontsize=10,
   bbox=dict(boxstyle='round,pad=.22',fc='#fffdf7',ec='none',alpha=.94),
   arrowprops=dict(arrowstyle='-',color='#667d80',lw=.6),zorder=4)
 ax.set_axis_off();ax.margins(x=.12,y=.15)
 labels=['Below 40%','40% to <45%','45% to <50%','50% to <55%','55% or more']
 fig.legend(handles=[Patch(facecolor=c,label=l) for c,l in zip(colors,labels)],loc='lower center',bbox_to_anchor=(.5,.078),ncol=5,frameon=False,fontsize=10)
 fig.text(.045,.035,'2020 to 2024 ACS estimates  •  Pennsylvania counties  •  Census Bureau B25070 and 2024 boundaries',fontsize=9,color='#51656e')
 fig.subplots_adjust(left=.025,right=.975,top=.88,bottom=.14)
 save(fig,'county-map')


def draw_comparison(selected,state):
 fig,ax=plt.subplots(figsize=(10.8,6.5));y=np.arange(len(selected))
 fig.suptitle('A higher share does not always mean more households',x=.04,y=.98,ha='left',fontsize=18,fontweight='bold')
 fig.text(.04,.92,'Six highest estimated county shares, plus Allegheny as a western urban comparison',fontsize=11)
 # Stop the reference line and band below their header label.
 ax.axvspan(state['lower90'],state['upper90'],ymax=.90,color='#c5d2ce',alpha=.5,zorder=0)
 ax.axvline(state['burden_pct'],ymax=.90,color='#60746e',linestyle='--',lw=1.3,zorder=1)
 ax.errorbar(selected.burden_pct,y,xerr=selected.moe90,fmt='o',color='#286b75',ecolor='#789a9e',capsize=3,ms=7,zorder=3)
 for i,(_,r) in enumerate(selected.iterrows()):
  ax.text(74,i,f'{r.burdened_households:,}',va='center',ha='right',fontsize=11,color='#415562')
 ax.set_yticks(y,selected.name);ax.invert_yaxis();ax.set_xlim(40,76)
 ax.set_xticks([40,45,50,55,60,65],[f'{v}%' for v in [40,45,50,55,60,65]])
 ax.text(74,-.8,'Households\nat or above 30%',ha='right',va='bottom',fontsize=10,fontweight='bold')
 ax.text(state['burden_pct'],-.7,f"PA {state['burden_pct']:.1f}%",ha='center',va='bottom',fontsize=10,color='#536b62')
 ax.set_xlabel('Share of renter households',labelpad=12)
 ax.set_ylim(len(selected)-.5,-1.1)
 for spine in ax.spines.values(): spine.set_visible(False)
 ax.tick_params(axis='y',length=0,pad=12);ax.tick_params(axis='x',length=0);ax.grid(axis='x',alpha=.15)
 fig.text(.04,.035,'Error bars show the precision of each estimate (90% confidence intervals).\n2020 to 2024 ACS  •  Includes renters paying rent whose rent share of income can be calculated.',fontsize=9,color='#51656e',linespacing=1.7)
 fig.subplots_adjust(left=.17,right=.98,top=.83,bottom=.19)
 save(fig,'county-comparison')


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
 for p in [RAW,RESULTS/'tables',RESULTS/'figures']:p.mkdir(parents=True,exist_ok=True)
 acquire(args.refresh)
 c,crep=summarize(read_vre('b25070_county.zip','0500000US42'))
 st,srep=summarize(read_vre('b25070_state.zip','0400000US42'));state=st.iloc[0].to_dict()
 assert len(c)==67 and len(st)==1 and c.geoid.is_unique
 for key in ['total_renter_households','eligible_households','burdened_households','severe_households','not_computed']:
  assert int(c[key].sum())==state[key],key
 geo=gpd.read_file(RAW/'counties_2024.zip');geo=geo[geo.STATEFP=='42'].copy()
 assert len(geo)==67 and geo.GEOID.is_unique and geo.crs is not None
 assert geo.is_valid.all() and not geo.geometry.is_empty.any()
 joined=geo[['GEOID','geometry']].merge(c,left_on='GEOID',right_on='geoid',validate='one_to_one',how='outer',indicator=True)
 assert (joined['_merge']=='both').all();joined=joined.drop(columns=['_merge','GEOID']).to_crs(5070)
 selected=c.sort_values(['burden_pct','geoid'],ascending=[False,True]).head(6)
 selected=pd.concat([selected,c[c.name=='Allegheny']]).drop_duplicates('geoid')
 # Preserve estimate intervals for all counties, rather than ranking noisy estimates as exact.
 c.sort_values('geoid').to_csv(RESULTS/'tables'/'county-burden.csv',index=False,float_format='%.8f')
 st.to_csv(RESULTS/'tables'/'state-burden.csv',index=False,float_format='%.8f')
 selected.to_csv(RESULTS/'tables'/'highlighted-counties.csv',index=False,float_format='%.8f')
 joined.to_file(RESULTS/'pa-rent-burden.gpkg',layer='county_burden',driver='GPKG')
 reopened=gpd.read_file(RESULTS/'pa-rent-burden.gpkg');assert len(reopened)==67 and reopened.crs.to_epsg()==5070
 philly=c[c.name=='Philadelphia'].iloc[0]
 stats=dict(state=state,counties={r['name']:r for r in c.to_dict('records')},
  county_count=len(c),counties_above_half=int((c.burden_pct>=50).sum()),
  philly_share_burdened=100*float(philly.burdened_households)/state['burdened_households'],
  outside_philly_pct=100*(state['burdened_households']-int(philly.burdened_households))/(state['eligible_households']-int(philly.eligible_households)),
  excluded_pct=100*state['not_computed']/state['total_renter_households'],
  severe_share_burdened=100*state['severe_households']/state['burdened_households'])
 (RESULTS/'summary.json').write_text(json.dumps(stats,indent=2)+'\n')
 style();draw_map(joined);draw_comparison(selected,state)
 versions={p:importlib.metadata.version(p) for p in ['geopandas','pandas','numpy','matplotlib','shapely','pyproj','pyogrio','requests']}
 (RESULTS/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),packages=versions),indent=2)+'\n')
 print(f"Validated 67 county joins, totals and replicate intervals. PA burden {state['burden_pct']:.2f}%; severe {state['severe_pct']:.2f}%.")
 print(selected[['name','burden_pct','moe90','burdened_households']].to_string(index=False))
 print(f"Counties at least half: {stats['counties_above_half']}; Philadelphia share of burdened households: {stats['philly_share_burdened']:.2f}%")

if __name__=='__main__':main()
