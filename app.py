"""Touchline: a transparent, local Premier League valuation workspace."""
from pathlib import Path
from html import escape
import io
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src.data_processing import validate_dataset
from src.model import evaluate, predict_nonnegative, NUMERIC_FEATURES, TARGET

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Touchline | Player Intelligence', page_icon='⚽', layout='wide')
st.markdown('''<style>
.block-container{max-width:1500px;padding-top:2.2rem;padding-bottom:3rem}
h1,h2,h3{letter-spacing:-.035em} h1{font-weight:750!important}
section[data-testid="stSidebar"]{border-right:1px solid #263244}
.hero{padding:28px 32px;border:1px solid #2a3c50;border-radius:18px;background:linear-gradient(115deg,#182b36,#141b2b 68%);margin-bottom:22px}
.eyebrow{color:#6ee7b7;font-size:11px;letter-spacing:.18em;font-weight:700;text-transform:uppercase}
.hero h1{font-size:38px;margin:5px 0}.hero p{color:#aab9cc;margin:0;font-size:15px}
[data-testid="stMetric"]{background:#141d2b;border:1px solid #263244;border-radius:12px;padding:17px 20px}
[data-testid="stMetricLabel"]{color:#9aacc1;font-size:12px}
[data-testid="stMetricValue"]{font-size:27px}
.stTabs [data-baseweb="tab-list"]{gap:24px;border-bottom:1px solid #263244}
.stTabs [data-baseweb="tab"]{padding:12px 2px}
.stTabs [aria-selected="true"]{color:#6ee7b7}
</style>''', unsafe_allow_html=True)
COLORS = {'Attacker':'#6ee7b7','Midfielder':'#7ea9ff','Defender':'#c4a0ff','Goalkeeper':'#ffc978'}


def money(value):
    return '—' if pd.isna(value) else f'€{value/1e6:,.2f}m'


def chart(fig, height=400):
    fig.update_layout(template='plotly_dark', height=height, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Arial',color='#acbdd0'), margin=dict(l=15,r=15,t=30,b=15),
                      legend=dict(orientation='h',y=1.12,title=''), hoverlabel=dict(bgcolor='#1b293d'))
    fig.update_xaxes(gridcolor='#243043',zeroline=False)
    fig.update_yaxes(gridcolor='#243043',zeroline=False)
    st.plotly_chart(fig, use_container_width=True)


def download_csv(frame, label, filename, key):
    # Neutralize spreadsheet formula injection in free-text imported fields.
    safe = frame.drop(columns=['_player_group'],errors='ignore').copy()
    for col in safe.select_dtypes(include=['object','string']):
        safe[col] = safe[col].map(lambda v: "'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    st.download_button(label, safe.to_csv(index=False).encode(), filename, 'text/csv', key=key)


@st.cache_resource(show_spinner=False, max_entries=5)
def analyze(raw, strategy):
    data, warnings = validate_dataset(pd.read_csv(io.BytesIO(raw)))
    model, metrics, result = evaluate(data, strategy)
    return data, warnings, model, metrics, result


workspace = st.sidebar.radio('Workspace', ['Valuation workspace', 'Live football'])
if workspace == 'Live football':
    from src.live_ui import render_live
    render_live()
    st.stop()

with st.sidebar:
    st.markdown('## ⚽ TOUCHLINE')
    st.caption('PLAYER INTELLIGENCE / PREMIER LEAGUE')
    st.divider()
    options = {'Demo · synthetic data': ROOT/'data/sample_dataset.csv'}
    if (ROOT/'data/processed_dataset.csv').exists():
        options['Local · processed dataset'] = ROOT/'data/processed_dataset.csv'
    source = st.selectbox('Dataset',list(options))
    upload = st.file_uploader('Import player-season CSV',type=['csv'])
    raw = upload.getvalue() if upload else options[source].read_bytes()
    strategy = st.selectbox('Validation method',['Player-held-out','Forward by season'],help='Player-held-out excludes every season of each tested player. Forward evaluation trains on earlier seasons and tests later seasons.')
    st.caption('Filters below affect browsing only. Evaluation always uses the full imported dataset.')

try:
    with st.spinner('Validating data and evaluating held-out predictions…'):
        dataset, warnings, model, metrics, result = analyze(raw,strategy)
except (ValueError, pd.errors.ParserError, UnicodeDecodeError) as exc:
    st.error(str(exc))
    st.info('Correct the CSV or choose another validation method. See README.md for the schema.')
    st.stop()

demo = (not upload and source.startswith('Demo')) or ('data_kind' in dataset and dataset.data_kind.eq('synthetic').any())
# Detect unmarked copies of the supplied demo as well.
reference = pd.read_csv(ROOT/'data/sample_dataset.csv')
core = ['name','season','goals','assists',TARGET]
if len(dataset)==len(reference):
    demo = demo or dataset[core].sort_values('name').reset_index(drop=True).equals(reference[core].sort_values('name').reset_index(drop=True))
status = 'SYNTHETIC DEMO' if demo else 'IMPORTED DATA · SOURCE NOT VERIFIED'
st.markdown(f'''<div class="hero"><div class="eyebrow">SCOUTING WORKSPACE / {status}</div>
<h1>Read the game. Question the price.</h1><p>Explore performance, compare player profiles, and test how well the numbers explain listed market values.</p></div>''',unsafe_allow_html=True)
if demo:
    st.warning('Demo mode: player names are real; statistics and market values are generated. These results do not describe today’s Premier League.')
else:
    st.info('Imported values are source estimates, not objective fair prices. Predictions measure agreement with those estimates; source accuracy and freshness require verification.')

with st.sidebar:
    st.divider()
    query = st.text_input('Search players',placeholder='Search a name…')
    seasons = st.multiselect('Seasons', sorted(dataset.season.astype(int).unique(),reverse=True),default=sorted(dataset.season.astype(int).unique(),reverse=True))
    positions = st.multiselect('Positions',list(COLORS),default=list(COLORS))
    clubs = st.multiselect('Clubs',sorted(dataset.team.unique()),placeholder='All clubs')
    min_apps = st.slider('Minimum appearances',0,42,0)
    st.divider()
    st.caption(f'{len(dataset):,} rows · {dataset._player_group.nunique():,} players')
    st.caption('Fixed ridge regression · 5 core features · EUR')

filtered = result[result.name.str.contains(query,case=False,regex=False) & result.season.isin(seasons) & result.position.isin(positions) & (result.appearances>=min_apps)]
if clubs:
    filtered = filtered[filtered.team.isin(clubs)]
cols = st.columns(4)
cols[0].metric('PLAYER-SEASONS IN VIEW',f'{len(filtered):,}')
cols[1].metric('LISTED VALUE · MEDIAN',money(filtered[TARGET].median()))
cols[2].metric('HELD-OUT ERROR · MAE',money(metrics['mae_eur']))
improvement = (1-metrics['mae_eur']/metrics['baseline_mae_eur'])*100 if metrics['baseline_mae_eur'] else None
cols[3].metric('VS POSITION MEDIAN BASELINE',f'{improvement:+.1f}%' if improvement is not None else '—')
st.caption('Model error and baseline comparison cover all evaluated rows. Positive baseline improvement means lower error.')
explore, dossier, compare, lab, diagnostics = st.tabs(['Market overview','Player dossier','Compare players','Scenario lab','Model & data quality'])

with explore:
    left,right=st.columns([3,1])
    left.subheader('The valuation landscape')
    right.caption('Above the line: model estimate exceeds listed value.')
    plotted=filtered.dropna(subset=['predicted_value_eur'])
    if filtered.empty:
        st.info('No players match these filters. Clear the search or broaden your selection.')
    elif plotted.empty:
        st.info('These rows are training-only in forward evaluation. Select a later season to view predictions.')
    else:
        a,b=st.columns([1.6,1])
        with a:
            fig=px.scatter(plotted,x=TARGET,y='predicted_value_eur',color='position',hover_name='name',hover_data=['team','season','goals','assists'],color_discrete_map=COLORS,labels={TARGET:'Listed market value (€)','predicted_value_eur':'Held-out model estimate (€)'})
            peak=max(plotted[TARGET].max(),plotted.predicted_value_eur.max())*1.06
            fig.add_shape(type='line',x0=0,y0=0,x1=peak,y1=peak,line=dict(color='#62758c',dash='dot'))
            fig.update_traces(marker=dict(size=10,opacity=.85,line=dict(width=1,color='#0b1018')))
            chart(fig)
        with b:
            st.markdown('**Largest model disagreements**')
            top=plotted.loc[plotted.gap_eur.abs().nlargest(10).index].sort_values('gap_eur')
            fig=px.bar(top,x='gap_eur',y=top.name+' · '+top.season.astype(int).astype(str),orientation='h',color='position',color_discrete_map=COLORS,labels={'gap_eur':'Estimate − listed value (€)','y':''})
            fig.update_layout(showlegend=False)
            chart(fig)
        st.caption('Disagreement is a research lead, not evidence that a player is underpriced or overpriced.')
    st.subheader('Scouting table')
    sort_by=st.selectbox('Sort by',['Listed value','Largest positive gap','Largest negative gap','Name'])
    sort_col, ascending={'Listed value':(TARGET,False),'Largest positive gap':('gap_eur',False),'Largest negative gap':('gap_eur',True),'Name':('name',True)}[sort_by]
    table=filtered.sort_values(sort_col,ascending=ascending)
    st.dataframe(table[['name','team','position','season','age','appearances','goals','assists',TARGET,'predicted_value_eur','gap_pct']],hide_index=True,use_container_width=True,column_config={TARGET:st.column_config.NumberColumn('Listed €',format='€%.0f'),'predicted_value_eur':st.column_config.NumberColumn('Held-out estimate €',format='€%.0f'),'gap_pct':st.column_config.NumberColumn('Gap %',format='%.1f%%')})
    download_csv(table,'Export filtered analysis','scouting-analysis.csv','scouting_export')


def label(index):
    r=result.loc[index]
    return f'{r["name"]} · {int(r.season)}/{str(int(r.season)+1)[-2:]} · {r.team}'

with dossier:
    st.subheader('A closer look')
    if filtered.empty:
        st.info('Broaden the sidebar filters to select a player.')
    else:
        selected=st.selectbox('Player & season',filtered.index.tolist(),format_func=label)
        row=result.loc[selected]
        st.markdown(f'### {escape(row["name"])}')
        st.caption(f'{row.team} · {row.position} · {row.age:g} years old · {int(row.appearances)} appearances')
        a,b,c=st.columns(3)
        a.metric('LISTED VALUE',money(row[TARGET]))
        b.metric('HELD-OUT ESTIMATE',money(row.predicted_value_eur))
        c.metric('MODEL GAP',f'{row.gap_pct:+.1f}%' if pd.notna(row.gap_pct) else '—')
        if pd.isna(row.predicted_value_eur):
            st.info('This is an earliest-season training row. No forward prediction is available.')
        else:
            st.caption(f'Prediction from validation fold {int(row.fold)}. '+('This player’s rows were excluded from training.' if strategy=='Player-held-out' else 'Only earlier seasons were used; prior seasons of this player may be included.'))
        peers=dataset[(dataset.position==row.position)&(dataset.season==row.season)]
        values=[]
        for feature in NUMERIC_FEATURES:
            values.append({'Metric':feature.title(),'Player':row[feature],'Peer median':peers[feature].median(),'Percentile':100*((peers[feature]<row[feature]).sum()+.5*(peers[feature]==row[feature]).sum())/len(peers)})
        a,b=st.columns([1.3,1])
        with a:
            st.markdown('**Position & season context**')
            chart(px.bar(pd.DataFrame(values),x='Percentile',y='Metric',orientation='h',range_x=[0,100],color_discrete_sequence=['#6ee7b7']),300)
        with b:
            st.markdown('**Profile details**')
            st.dataframe(pd.DataFrame(values).round(1),hide_index=True,use_container_width=True)
            st.caption(f'Compared with {len(peers)} rows in the same position and season, including this player. Higher age percentile means older, not better.')
        if row.position in ['Defender','Goalkeeper']:
            st.warning('This feature set lacks defensive and shot-stopping data. Treat this position’s estimate with particular caution.')
        download_csv(result.loc[[selected]],'Export player report','player-report.csv','player_export')

with compare:
    st.subheader('Side-by-side scouting')
    chosen=st.multiselect('Choose up to four player-seasons',filtered.index.tolist(),default=filtered.index[:2].tolist(),format_func=label,max_selections=4)
    if chosen:
        comparison=result.loc[chosen].copy()
        comparison['player_season']=[label(i) for i in chosen]
        st.dataframe(comparison.set_index('player_season')[['position','age','appearances','goals','assists',TARGET,'predicted_value_eur','gap_pct']].T,use_container_width=True)
        melted=comparison.melt(id_vars=['player_season'],value_vars=[TARGET,'predicted_value_eur'],var_name='Measure',value_name='EUR')
        chart(px.bar(melted,x='player_season',y='EUR',color='Measure',barmode='group',color_discrete_sequence=['#7ea9ff','#6ee7b7'],labels={'player_season':''}))
        st.caption('Raw season totals depend on playing time. Cross-season comparisons also reflect different market conditions.')
    else:
        st.info('Select players to compare their profiles.')

with lab:
    st.subheader('Explore a hypothetical profile')
    st.caption('This uses the final model fitted on all rows. It is exploratory and is not a held-out accuracy test.')
    with st.form('scenario'):
        a,b=st.columns(2)
        position=a.selectbox('Position',sorted(dataset.position.unique()),key='scenario_position')
        age=a.slider('Age',16,40,24)
        apps=a.slider('League appearances',0,42,25)
        goals=b.slider('Goals',0,50,10)
        assists=b.slider('Assists',0,35,8)
        listed=b.number_input('Comparison value (€ millions)',min_value=0.0,value=30.0,step=1.0)
        submit=st.form_submit_button('Estimate this profile',type='primary')
    if submit:
        custom=pd.DataFrame([dict(position=position,age=age,appearances=apps,goals=goals,assists=assists)])
        if apps==0 and (goals or assists):
            st.error('A player with zero appearances cannot have goals or assists.')
        else:
            predicted=predict_nonnegative(model,custom)[0]
            a,b=st.columns(2)
            a.metric('SCENARIO ESTIMATE',money(predicted))
            b.metric('VS YOUR COMPARISON VALUE',money(predicted-listed*1e6))
            peers=dataset[dataset.position==position]
            outside=[c for c in NUMERIC_FEATURES if not peers[c].min()<=custom[c].iloc[0]<=peers[c].max()]
            if outside:
                st.warning('Outside observed same-position ranges: '+', '.join(outside)+'. Extrapolation is unreliable.')
            st.caption('No calibrated confidence interval is available. Average validation error is not an individual prediction interval.')

with diagnostics:
    st.subheader('Evidence before confidence')
    a,b,c=st.columns(3)
    a.metric('HELD-OUT RMSE',money(metrics['rmse_eur']))
    b.metric('HELD-OUT R²',f'{metrics["r2"]:.3f}' if metrics['r2'] is not None else 'Undefined')
    c.metric('EVALUATED ROWS',f'{metrics["n_test"]} / {len(dataset)}')
    st.caption('MAE = mean absolute error. RMSE penalizes large errors. Negative R² means worse than a constant test-set mean reference.')
    if improvement is not None and improvement <= 0:
        st.warning('The model does not outperform the simple position-median baseline on these validation splits.')
    for message in warnings:
        st.warning(message)
    if strategy=='Player-held-out':
        st.info('All seasons of each tested player stay outside that fold’s training data. This estimates generalization to unseen players, not forecasting future seasons.')
    else:
        st.info('Each season is tested using only earlier seasons. The earliest season is training-only. Season ordering cannot fix incorrectly dated source snapshots.')
    a,b=st.columns(2)
    with a:
        st.markdown('**Error by position**')
        evaluated=result.dropna(subset=['predicted_value_eur'])
        grouped=evaluated.groupby('position').agg(rows=('name','size'),mae_eur=('absolute_error_eur','mean')).reset_index()
        chart(px.bar(grouped,x='position',y='mae_eur',color='position',color_discrete_map=COLORS,hover_data=['rows'],labels={'mae_eur':'Held-out MAE (€)','position':''}),320)
    with b:
        st.markdown('**Validation folds**')
        st.dataframe(pd.DataFrame(metrics['folds']),hide_index=True,use_container_width=True)
        st.caption('A fixed regularized linear model is used. No model is selected on these validation results. Numeric scaling is learned within each training fold.')
    with st.expander('Data contract & next data to collect'):
        st.write('Required: name, position, team, season, age, appearances, goals, assists, transfer_value_eur. One row per player per season; values in whole EUR.')
        st.write('Add stable player_id, stats_as_of, valuation_date, value_source, and data_kind. Start with historical, date-aligned market values and complete league coverage; then minutes, xG/xA, defensive and goalkeeper stats, contract months and injury availability.')
        st.write('Extra performance columns are retained in exports but are not silently added to the model. Extending the feature set requires validation and a fresh evaluation.')
        st.write('The football-data.org scorers endpoint is a scoring leaderboard, not a complete league player sample. This can bias any model trained on that feed.')
    st.download_button('Download evaluation summary',json.dumps(metrics,indent=2,allow_nan=False),'evaluation-summary.json','application/json')
    download_csv(result,'Download all held-out predictions','held-out-predictions.csv','all_export')
    template=','.join(['player_id','name','position','team','season','age','appearances','goals','assists','transfer_value_eur','stats_as_of','valuation_date','value_source','data_kind'])+'\n'
    st.download_button('Download CSV template',template,'player-season-template.csv','text/csv')
st.divider()
st.caption('TOUCHLINE / Research workspace · Listed market values are estimates, not transaction prices. Use Live football in the sidebar for current API data; valuation data comes from the selected CSV.')
