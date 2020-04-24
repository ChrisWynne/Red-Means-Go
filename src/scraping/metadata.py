# import os
# import sys
# import json
# import pandas as pd
# import requests
# from scipy.stats import zscore

# sys.path.insert(0, os.path.abspath('../../src/scraping'))
# import youtube_requesting as ytr


# def fetch_raw_data(fp, cfg):
#     data = {}
# #     fp = ROOT_DIR + cfg["videos-dir"] + cfg["selected-game"] + '/'
#     for fname in os.listdir(fp):
#         if fname.endswith(".json"):
#             with open(fp + fname) as f:
#                 read_data = json.load(f)
#             data[read_data["date_scraped"]] = read_data["data"]
            
#     return data

# def get_vid_metadata(vid_data, api_key, mdata):
# #     api_service_name = "youtube"
# #     api_version = "v3"
#     unwanted_keys = ['liveBroadcastContent', 'localized', 'defaultAudioLanguage']
    
#     vid_id = vid_data["video_id"]
    
# #     mdata = ytr.request_video_details(vid_id, api_key, api_service_name, api_version)['items']
#     out = mdata["statistics"]
    
#     for key in unwanted_keys:
#         if key in mdata["snippet"]:
#             mdata["snippet"].pop(key)
    
#     out.update(mdata["snippet"])
#     out.update(vid_data)
    
#     return out


# def request_data(vid_id, api_key):
#     api_service_name = "youtube"
#     api_version = "v3"
    
#     mdata = ytr.request_video_details(vid_id, api_key, api_service_name, api_version)['items']
#     if len(mdata) == 0:
#         return None
    
#     return mdata[0]


# def make_mdata_df(data, api_key):
#     metadata = []

#     for vid in data:
#         temp_dict = {
#             "video_id":vid["video_id"],
#             "position":vid["position"],
#             "channel_videos":vid["channel_videos"]
#         }
#         mdata = request_data(vid["video_id"], api_key)
#         if mdata is None:
#             continue
#         mdata = get_vid_metadata(vid, api_key, mdata)
#         temp_dict.update(mdata)
        
#         metadata.append(temp_dict)
    
#     return pd.DataFrame(metadata)

import pandas as pd
import json
import os
import json
import pandas as pd
import time
from PIL import Image
import requests
from io import BytesIO
import numpy as np
from datetime import datetime
import dateutil.relativedelta
from dateutil.parser import parse
from scipy import stats
import ast
import sys

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors


def channel_video_success(row, weights=None):
    metric_cols = ["z_comments", "z_dislikes",
                   "z_likes", "z_views"]
    if weights is None:
        weights = [1 for _ in metric_cols]
    
    scores = [row[key] for key in metric_cols]
    return sum(scores)


def check_vid_game(vid_stats, game_title):
    game_title = game_title.lower()
    try:
        tags = vid_stats['tags']
    except:
        tags = []
    try:
        title = vid_stats['title'].lower()
    except:
        title = np.nan
    try:
        description = vid_stats['description'].lower()
    except:
        description = np.nan
    if type(tags) == float:
        tags = []
    if type(title) == float:
        title = ""
    if type(description) == float:
        description = "" 
    if game_title in title or game_title in description:
        return True
    else:
        for tag in tags:
            if game_title in tag.lower():
                return True
    return False


def download_vid_thumb(video_id, df, save_dir, res):
    dict_val = df[df.videoId == video_id]["thumbnails"].iloc[0]
    if pd.isnull(dict_val):
        return
    if isinstance(dict_val, str):
        url = eval(dict_val)[res]["url"]
    else:
        url = dict_val[res]["url"]
    with open(save_dir + video_id + ".jpg", 'wb') as f:
        f.write(requests.get(url).content)
        
def download_df_thumbs(df, save_dir, res):
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    num_thumbnails = len(df['videoId'])
    count = 0
    for v_id in df["videoId"]:
        if count % 25 == 0:
            print("Thumbnail Download:", count, "of", num_thumbnails)
        count += 1
        if os.path.exists(save_dir + v_id + ".jpg"):
            continue
        else:
            download_vid_thumb(v_id, df, save_dir, res)
    print("Thumbnails Successfully Downloaded!")
        
        
def generate_metadata(master_dic, data, game_title, api_keys, api_service_name, api_version):
    all_metadata = pd.DataFrame()
    progress_count = 0
    for searched_vid in data['data']:
        if progress_count % 25 == 0:
            print("Metadata Progress:",progress_count,"of",len(data['data']))
        channel_game_vids = []
        for channel_vid in searched_vid['channel_videos']:
            if channel_vid in master_dic.keys():
                cur_vid_details = master_dic[channel_vid]
                cur_vid_stats = get_vid_stats(cur_vid_details)
                if check_vid_game(cur_vid_stats, game_title):
                    channel_game_vids.append(cur_vid_stats)
            else:
                # TODO: Handle missing / incorrect API key
                try:
                    api_key = api_keys[api_idx]
                    api_idx += 1
                    if api_idx == len(api_keys):
                        api_idx = 0
                    cur_vid_details = request_video_details(channel_vid,
                                                            api_key,
                                                            api_service_name,
                                                            api_version)
                    if len(cur_vid_details['items']) == 0:
                        cur_vid_details = {}
                    else:
                        cur_vid_details = cur_vid_details['items'][0]
                    master_dic[channel_vid] = cur_vid_details
                    cur_vid_stats = get_vid_stats(cur_vid_details)
                    if check_vid_game(cur_vid_stats, game_title):
                        channel_game_vids.append(cur_vid_stats)
                except:
                    print("Video was not in local storage and there was a problem scraping:")
                    print(sys.exc_info()[0])
                    raise
        cur_metadata = pd.DataFrame(channel_game_vids)
        cur_metadata['tags'] = cur_metadata['tags'].apply(lambda x: str(x))
        cur_metadata['thumbnails'] = cur_metadata['thumbnails'].apply(lambda x: str(x))
        cur_metadata['z_views'] = stats.zscore(cur_metadata['viewCount'])
        cur_metadata['z_likes'] = stats.zscore(cur_metadata['likeCount'])
        cur_metadata['z_dislikes'] = stats.zscore(cur_metadata['dislikeCount'])
        cur_metadata['z_comments'] = stats.zscore(cur_metadata['commentCount'])
        all_metadata = pd.concat([all_metadata,cur_metadata],sort=True).reset_index(drop=True)
        progress_count += 1
    unique_metadata = all_metadata.drop_duplicates().reset_index(drop=True)
    return unique_metadata


def generate_search_result_df(unique_metadata,data):
    out_data = []
    for searched_vid in data['data']:
        if searched_vid['video_id'] in unique_metadata['videoId'].values:
            vid_stats = unique_metadata[unique_metadata['videoId'] == searched_vid['video_id']].iloc[0]
            vid_stats['position'] = searched_vid['position']
            out_data.append(vid_stats)
        else:
            all_nans = unique_metadata.iloc[0].apply(lambda x: np.nan)
            all_nans['videoId'] = searched_vid['video_id']
            all_nans['position'] = searched_vid['position']
            out_data.append(all_nans)
    out_df = pd.DataFrame(out_data).reset_index(drop=True)
    return out_df
        
        
def get_success_metrics(df):
    df["global_success"] = df.apply(global_video_success, axis=1)
    df["global_success"] = zscore(df["global_success"], nan_policy="omit")
    df["channel_success"] = df.apply(channel_video_success, axis=1)
    
    return df


def get_vid_stats(vid):
    try:
        vid_id = vid['id']
    except:
        vid_id = np.nan
    try:
        channel_id = vid['snippet']['channelId']
    except:
        channel_id = np.nan
    try:
        channel_title = vid['snippet']['channelTitle']
    except:
        channel_title = np.nan
    try:
        thumbnail_links = vid['snippet']['thumbnails']
    except:
        thumbnail_links = np.nan
    try:
        title = vid['snippet']['title']
    except:
        title = np.nan
    try:
        language = vid['snippet']['defaultAudioLanguage']
    except:
        language = np.nan
    try:
        date = parse(vid['snippet']['publishedAt'])
    except:
        date = np.nan
    try:
        duration = vid['contentDetails']['duration']
    except:
        duration = np.nan
    try:
        views = vid['statistics']['viewCount']
    except:
        views = np.nan
    try:
        likes = vid['statistics']['likeCount']
    except:
        likes = np.nan
    try:
        dislikes = vid['statistics']['dislikeCount']
    except:
        dislikes = np.nan
    try:
        comments = vid['statistics']['commentCount']
    except:
        comments = np.nan
    try:
        favorites = vid['statistics']['favoriteCount']
    except:
        favorites = np.nan
    try:
        description = vid['snippet']['description']
    except:
        description = np.nan
    try:
        tags = vid['snippet']['tags']
    except:
        tags = np.nan
    try:
        cat_id = vid['snippet']['categoryId']
    except:
        cat_id = np.nan
    stats = {"videoId": vid_id,
             "channelId":channel_id,
             "channelTitle":channel_title,
             "thumbnails":thumbnail_links,
             "title":title,
             "date":date,
             "duration": duration,
             "viewCount":float(views),
             "likeCount":float(likes),
             "dislikeCount":float(dislikes),
             "commentCount":float(comments),
             "favoriteCount":float(favorites),
             "tags":tags,
             "defaultLanguage":language,
             "categoryId":float(cat_id),
             "description": description}
    return stats

        
def global_video_success(row, weights=None):
    metric_cols = ["commentCount", "dislikeCount", "favoriteCount",
                   "likeCount", "viewCount"]
    if weights is None:
        weights = [1 for _ in metric_cols]
    weights[1] = -1
    
    scores = [row[key] for key in metric_cols]
    return sum(scores)


def init_master_dic(dic_fp):
    if dic_fp == None:
        return {}
    elif not os.path.exists(dic_fp):
        print("Requests Dictionary path does not exist. If you do not have a local requests dic, enter None")
        raise ValueError
    with open(dic_fp) as json_file:
        out_dic = json.load(json_file)
    return out_dic
    
    
def metadata_main(api_keys, api_service_name, api_version,
                  out_fp, master_dic_write_fp, 
                  init_data_fp, game_title, master_dic_fp):
    
    master_dic = init_master_dic(master_dic_fp)
    with open(init_data_fp) as json_file:
        data = json.load(json_file)
        
    all_metadata = generate_metadata(master_dic, data, game_title, api_keys, api_service_name, api_version)
    
    if len(master_dic.keys()) > 0:
        save_requests_dic(master_dic_write_fp, master_dic)
        
    out_df = generate_search_result_df(all_metadata, data)
    out_df.to_csv(out_fp,index=False)
    print("Metadata Saved at: " + out_fp)
    return out_df

def request_video_details(video_id, api_key, api_service_name, api_version):
    """API cost of 7"""
    youtube = googleapiclient.discovery.build(
        api_service_name, api_version, developerKey=api_key)
    # note that this uses youtube.videos instead of youtube.search
    request = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=video_id
    )
    response = request.execute()
    return response

def save_requests_dic(fp, data):
    with open(fp,"w") as json_file:
        json.dump(data, json_file)
    print("API Requests logged locally at: " + fp)
