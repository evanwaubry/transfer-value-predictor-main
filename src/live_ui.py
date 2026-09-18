"""On-demand live views, independent of the valuation dataset and model."""
from datetime import datetime, timedelta, timezone
import hashlib
import time
import pandas as pd
import streamlit as st
from src.football_api import api_key, request, recent_matches, current_scorers, score_label, FootballAPIError
from src.data_processing import build_features, merge_with_transfer_values, validate_dataset


def csv_download(frame,label,filename,key):
    safe=frame.copy()
    for col in safe.select_dtypes(include=['object','string']):
        safe[col]=safe[col].map(lambda v:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    st.download_button(label,safe.to_csv(index=False).encode(),filename,'text/csv',key=key)


def fetch_action(callback):
    if time.monotonic()-st.session_state.get('last_live_request',-1000)<15:
        st.warning('Please wait 15 seconds between refreshes to conserve your API allowance.')
        return None
    st.session_state.last_live_request=time.monotonic()
    try:
        with st.spinner('Contacting football-data.org…'):
            return callback()
    except FootballAPIError as exc:
        st.error(str(exc))
        return None


def render_live():
    # Only a fingerprint is retained for detecting changed credentials. Responses are session-local.
    fingerprint=hashlib.sha256(api_key().encode()).hexdigest()
    if st.session_state.get('live_key_fingerprint')!=fingerprint:
        for key in ['match_snapshot','scorer_snapshot','last_live_request']:
            st.session_state.pop(key,None)
        st.session_state.live_key_fingerprint=fingerprint
    st.markdown('<div class="hero"><div class="eyebrow">TOUCHLINE / LIVE FOOTBALL</div><h1>The week in football.</h1><p>Premier League results, fixtures and the latest available scoring leaderboard.</p></div>',unsafe_allow_html=True)
    st.caption('On-demand data · Free-plan scores may be delayed · Dates and kickoff times use UTC · Independent of the demo valuation dataset')
    matches,scorers,setup=st.tabs(['Recent matches','Current-season stats','API setup'])
    with setup:
        st.subheader('Connect your football-data.org account')
        st.markdown('1. [Create an account](https://www.football-data.org/client/register) and obtain your API token.\n2. In the project folder beside app.py, copy `.env.example` to `.env`.\n3. Replace the placeholder with your token and save the file.')
        st.code('FOOTBALL_DATA_API_KEY=your_token_here',language='bash')
        st.caption('The key is read locally and sent only as the authentication header to football-data.org. Do not include .env in a shared project ZIP or Git commit.')
        st.write('Key configured.' if api_key() else 'No key configured yet.')
        if st.button('Test API connection',key='test_connection'):
            payload=fetch_action(lambda:request('/competitions/PL'))
            if payload is not None:
                season=payload.get('currentSeason') or {}
                st.success(f"Connected to {payload.get('name','Premier League')}. Provider season: {season.get('startDate','unknown')} to {season.get('endDate','unknown')}.")
        st.markdown('[Check plan coverage and pricing](https://www.football-data.org/pricing). Match results and scorer access are separate capabilities. A 403 on scorers can occur even when match results work.')
        st.info('Connecting the API does not replace the valuation demo automatically. Load current stats, supply matching dated market values, then import the prepared CSV into Valuation workspace.')
    with matches:
        today=datetime.now(timezone.utc).date()
        with st.form('match_query'):
            period=st.selectbox('Date window',['Past week','Next week','Custom range'])
            st.caption('Past week means today and the previous six UTC calendar dates. Custom dates apply only when Custom range is selected.')
            dates=st.date_input('Custom dates',(today-timedelta(days=6),today))
            load=st.form_submit_button('Load / refresh matches',type='primary')
        if load:
            if period=='Past week':
                start,end=today-timedelta(days=6),today
            elif period=='Next week':
                start,end=today+timedelta(days=1),today+timedelta(days=7)
            elif isinstance(dates,(tuple,list)) and len(dates)==2:
                start,end=dates
            else:
                start=end=None
                st.warning('Select both a start and end date.')
            if start is not None:
                payload=fetch_action(lambda:recent_matches(start,end))
                if payload is not None:
                    st.session_state.match_snapshot=dict(rows=payload,start=str(start),end=str(end),fetched=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
        snapshot=st.session_state.get('match_snapshot')
        if snapshot is None:
            st.info('Load the past week to see recent matches. Add your key in API setup first; no valuation CSV is needed.')
        else:
            st.caption(f"Showing {snapshot['start']} through {snapshot['end']} · Fetched {snapshot['fetched']}. Change controls and press Load / refresh to replace this snapshot.")
            rows=snapshot['rows']
            clubs=sorted({(m.get(side) or {}).get('name','Unknown') for m in rows for side in ['homeTeam','awayTeam']})
            a,b=st.columns(2)
            club=a.selectbox('Club',['All clubs']+clubs)
            status=b.selectbox('Match status',['All statuses','Finished','Upcoming','In progress','Postponed / cancelled'])
            status_sets={'Finished':{'FINISHED','AWARDED'},'Upcoming':{'SCHEDULED','TIMED'},'In progress':{'IN_PLAY','PAUSED','EXTRA_TIME','PENALTY_SHOOTOUT'},'Postponed / cancelled':{'POSTPONED','CANCELLED','SUSPENDED'}}
            visible=[m for m in rows if (club=='All clubs' or club in [(m.get(s) or {}).get('name') for s in ['homeTeam','awayTeam']]) and (status=='All statuses' or m.get('status') in status_sets[status])]
            c1,c2=st.columns(2)
            c1.metric('MATCHES IN VIEW',len(visible))
            c2.metric('FINISHED',sum(m.get('status')=='FINISHED' for m in visible))
            if not visible:
                st.info('No matches in this range match the filters. Try another week, or clear the club/status filter.')
            exports=[]
            for m in visible:
                home=(m.get('homeTeam') or {}).get('name','Unknown')
                away=(m.get('awayTeam') or {}).get('name','Unknown')
                kickoff=pd.to_datetime(m['utcDate'],utc=True).strftime('%a %d %b · %H:%M UTC')
                with st.container(border=True):
                    a,b,c=st.columns([4,2,4])
                    a.markdown(f'**{home}**')
                    b.markdown(f'### {score_label(m)}')
                    c.markdown(f'**{away}**')
                    st.caption(f"{kickoff} · {m.get('status','Unknown').replace('_',' ').title()} · Matchday {m.get('matchday') or '—'}")
                    with st.expander('Match details'):
                        half=(m.get('score') or {}).get('halfTime') or {}
                        st.write(f"Half-time: {half.get('home') if half.get('home') is not None else '—'} – {half.get('away') if half.get('away') is not None else '—'}")
                        st.write(f"Venue: {m.get('venue') or 'Not supplied'}")
                        referees=', '.join(r.get('name','') for r in m.get('referees',[]) if r.get('name'))
                        st.write('Officials: '+(referees or 'Not supplied'))
                        st.caption('Provider last update: '+str(m.get('lastUpdated') or 'Not supplied'))
                        st.caption('Lineups, scorers and detailed match statistics are not requested by this basic results view.')
                exports.append({'match_id':m['id'],'utcDate':m['utcDate'],'home':home,'away':away,'score':score_label(m),'status':m.get('status'),'matchday':m.get('matchday')})
            if exports:
                csv_download(pd.DataFrame(exports),'Download matches CSV','premier-league-matches.csv','matches_export')
    with scorers:
        st.subheader('Current-season scoring leaderboard')
        st.caption('The API identifies the season automatically. This is a scorers sample, not full Premier League player coverage.')
        st.info('Early-season totals reflect fewer matches than full-season totals. Use comparable observation windows; more recent data does not automatically make valuations more accurate.')
        if st.button('Load / refresh current-season stats',type='primary'):
            payload=fetch_action(current_scorers)
            if payload is not None:
                season,rows=payload
                st.session_state.scorer_snapshot=dict(season=season,rows=rows,fetched=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
        snapshot=st.session_state.get('scorer_snapshot')
        if snapshot is None:
            st.info('Load the latest available scorer data from your API account.')
        elif not snapshot['rows']:
            st.info('The provider returned no scorers for its current season. The season may not have started, or the feed may not yet be populated.')
        else:
            st.caption(f"Season: {snapshot['season'].get('startDate')} to {snapshot['season'].get('endDate')} · Fetched {snapshot['fetched']}")
            frame=build_features(snapshot['rows'])
            cutoff=min(pd.Timestamp.now(tz='UTC').date(),pd.Timestamp(snapshot['season']['endDate']).date()) if snapshot['season'].get('endDate') else pd.Timestamp.now(tz='UTC').date()
            dob=pd.to_datetime(frame.date_of_birth,errors='coerce')
            frame['age']=((pd.Timestamp(cutoff)-dob).dt.days/365.25).round(2)
            frame['age_as_of']=str(cutoff)
            search=st.text_input('Find a scorer')
            st.dataframe(frame[frame.name.str.contains(search,case=False,regex=False)][['name','team','season','position','goals','assists','appearances']],hide_index=True,use_container_width=True)
            csv_download(frame,'Download current stats CSV','current-season-stats.csv','stats_export')
            st.warning('Missing appearances or other fields must be filled from a reliable source. Match results do not supply individual season appearances, and missing values are not zero.')
            st.markdown('**Prepare data for the valuation model**')
            st.caption('Upload market values with exact name (or matching football-data.org player_id), season and transfer_value_eur. Include valuation_date and value_source. Dates must align with the stats snapshot; a retrieval timestamp alone does not verify alignment.')
            values=st.file_uploader('Matching market values CSV',type='csv',key='live_market_values')
            if values is not None:
                try:
                    merged=merge_with_transfer_values(frame,pd.read_csv(values))
                    clean,warnings=validate_dataset(merged)
                    for warning in warnings:
                        st.warning(warning)
                    csv_download(clean.drop(columns=['_player_group']),'Download prepared valuation dataset','current-valuation-dataset.csv','prepared_export')
                    st.success('Switch to Valuation workspace and upload this prepared dataset. Review the held-out errors before interpreting estimates.')
                except (ValueError,pd.errors.ParserError,UnicodeDecodeError) as exc:
                    st.error(str(exc))
                    st.info('You can download the raw current stats, fill missing fields and merge with verified values outside the app, then upload the complete CSV.')
    st.divider()
    st.markdown('Football data provided by the [Football-Data.org API](https://www.football-data.org/).')
