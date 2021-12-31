import os
import datetime

# 設定データの取得
# auther kenji uehara
# version 1.0.0
# since 2021-11-5
class ConfigX:
    
    def getConfigs(self, text_fn):
        configs = {}
        
        # 設定ファイルを読み込み
        f = open(text_fn, 'r', encoding='UTF-8')
        text_all = f.read()
        f.close()
            
        lines = text_all.split('\n')
        for line in lines:
            if ('=' in line) == False: continue
            field = self.__stringLeft(line, '=');
            field = field.strip()
            value = self.__stringRight(line, '=');
            value = value.strip()
            configs[field] = value
            
        configs = self.__setOutputFps(configs) # 入力ファイルパスから出力ファイルパスを自動生成する（出力ファイルパスが無い場合）

        return configs
    
    # 入力ファイルパスから出力ファイルパスを自動生成する（出力ファイルパスが無い場合）
    def __setOutputFps(self, configs) :
        
        # 自動生成する出力ファイルパス
        field_mp4 = 'output_mp4_fp'
        field_mp3 = 'output_mp3_fp'
        
        if not configs.get('input_mp4_fp'): return configs
        input_mp4_fp = configs['input_mp4_fp']
      
        time_fomat = configs['time_fomat']
        dt = datetime.datetime.now()
        u = dt.strftime(time_fomat)
        
        left_path = self.__stringLeftRev(input_mp4_fp, '.')
        print(left_path)
        
        if not configs.get(field_mp4):
            configs[field_mp4] = left_path + '_' + u + '.mp4'
            
        if not configs.get(field_mp3):
            configs[field_mp3] = left_path + '_' + u + '.mp3'
            
        return configs
    
    
    # 文字列を左側から印文字を検索し、左側の文字を切り出す
    # @param string s 対象文字列
    # @param $mark 印文字
    # @return 印文字から左側の文字列
    def __stringLeft(self, s, mark):
        a =s.find(mark)
        res = s[0:a]
        return res
    
    
    # 文字列を左側から印文字を検索し、右側の文字を切り出す。
    # @param string s 対象文字列
    # @param $mark 印文字
    # @return 印文字から右側の文字列
    def __stringRight(self, s, mark):
        a =s.find(mark)
        res = s[a+len(mark):]
        return res
    
    # 文字列を右側から印文字を検索し、右側の文字を切り出す
    # @param string s 対象文字列
    # @param $mark 印文字
    # @return 印文字から右側の文字列
    def __stringRightRev(self, s, mark):
        a =s.rfind(mark)
        res = s[a+len(mark):]
        return res
    
    
    # 文字列を右側から印文字を検索し、左側の文字を切り出す
    # @param string s 対象文字列
    # @param $mark 印文字
    # @return 印文字から左側の文字列
    def __stringLeftRev(self, s, mark):
        a =s.rfind(mark)
        res = s[0:a]
        return res
        