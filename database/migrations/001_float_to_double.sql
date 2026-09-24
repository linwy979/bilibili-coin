-- 將金額與數量欄位由 FLOAT 改為 DOUBLE
-- FLOAT 讀取時只保留 6 位有效數字，餘額 4,984,965 會被讀成 4,984,970，造成每次交易累積誤差
-- 已用舊版 schema 建立的資料庫請執行一次：mysql -u root -p bilibili < database/migrations/001_float_to_double.sql

ALTER TABLE `user_list`     MODIFY `balance`  DOUBLE DEFAULT 5000000;
ALTER TABLE `history_trade` MODIFY `quantity` DOUBLE DEFAULT NULL,
                            MODIFY `price`    DOUBLE DEFAULT NULL;
ALTER TABLE `price`         MODIFY `price`    DOUBLE DEFAULT NULL;
ALTER TABLE `price_history` MODIFY `price`    DOUBLE DEFAULT NULL;
