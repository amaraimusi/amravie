
import os
import pprint
import datetime
from vendor.CrudBase.ConfigX import ConfigX

print('mp4ファイル名一括変更')

configX = ConfigX();
configs = configX.getConfigs('./file_rename.txt');


import os
import datetime

# フォーマット済みの現在日付を取得
#now = datetime.datetime.now().strftime("%Y%m%d")

# 対象ディレクトリのパス
target_dir = configs['target_dir'];

# ディレクトリ内のファイルを走査
for filename in os.listdir(target_dir):
    # mp4ファイルのみ処理対象とする
    if filename.endswith(".mp4"):
        
        mtime = os.path.getmtime(os.path.join(target_dir, filename))
        #update_date = datetime.datetime.fromtimestamp(mtime).strftime("%Y/%m/%d %H:%M:%S")
        update_date = datetime.datetime.fromtimestamp(mtime).strftime("%m%d")
        
        # ファイル更新日を付け足した新しいファイル名を生成
        new_filename = f"{update_date}_{filename[:-4]}.mp4"
        
        print(new_filename)
        # ファイル名を変更
        os.rename(os.path.join(target_dir, filename), os.path.join(target_dir, new_filename))


print('Success')