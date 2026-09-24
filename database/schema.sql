-- 幣哩幣哩 BiliBili Coin 資料庫結構
-- 相容 MySQL 8 / MariaDB 10.4
-- 用法：mysql -u root -p bilibili < database/schema.sql

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `user_list` (
  `user_id` VARCHAR(50) NOT NULL COMMENT 'LINE User ID',
  `balance` DOUBLE DEFAULT 5000000 COMMENT '模擬現金餘額',
  PRIMARY KEY (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `coin_list` (
  `coin_id` VARCHAR(10) NOT NULL COMMENT '幣種代號，如 BTC',
  `coin_name` VARCHAR(50) DEFAULT NULL COMMENT 'CoinGecko ID，如 bitcoin',
  PRIMARY KEY (`coin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `follow_list` (
  `user_id` VARCHAR(50) NOT NULL,
  `coin_id` VARCHAR(10) NOT NULL,
  PRIMARY KEY (`user_id`, `coin_id`),
  KEY `coin_id` (`coin_id`),
  CONSTRAINT `follow_list_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_list` (`user_id`),
  CONSTRAINT `follow_list_ibfk_2` FOREIGN KEY (`coin_id`) REFERENCES `coin_list` (`coin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `history_trade` (
  `user_id` VARCHAR(50) NOT NULL,
  `coin_id` VARCHAR(10) NOT NULL,
  `quantity` DOUBLE DEFAULT NULL,
  `price` DOUBLE DEFAULT NULL COMMENT '成交價',
  `action` ENUM('buy', 'sell') DEFAULT NULL,
  `trade_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `coin_id`, `trade_time`),
  KEY `coin_id` (`coin_id`),
  CONSTRAINT `history_trade_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_list` (`user_id`),
  CONSTRAINT `history_trade_ibfk_2` FOREIGN KEY (`coin_id`) REFERENCES `coin_list` (`coin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `price` (
  `coin_id` VARCHAR(10) NOT NULL,
  `price` DOUBLE DEFAULT NULL,
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`coin_id`),
  CONSTRAINT `price_ibfk_1` FOREIGN KEY (`coin_id`) REFERENCES `coin_list` (`coin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE IF NOT EXISTS `price_history` (
  `coin_id` VARCHAR(10) NOT NULL,
  `price` DOUBLE DEFAULT NULL,
  `receiving_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`coin_id`, `receiving_time`),
  CONSTRAINT `price_history_ibfk_1` FOREIGN KEY (`coin_id`) REFERENCES `coin_list` (`coin_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 管理員帳號；首次啟動管理後台時，會依 get.env 自動建立二級管理員
CREATE TABLE IF NOT EXISTS `ROOT` (
  `account` VARCHAR(50) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `level` INT NOT NULL DEFAULT 1 COMMENT '1 = 一級管理員、2 = 二級管理員',
  PRIMARY KEY (`account`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 預設支援的幣種
INSERT INTO `coin_list` (`coin_id`, `coin_name`) VALUES
  ('BTC',  'bitcoin'),
  ('ETH',  'ethereum'),
  ('USDT', 'tether'),
  ('XRP',  'ripple'),
  ('BNB',  'binancecoin'),
  ('SOL',  'solana'),
  ('USDC', 'usd-coin'),
  ('DOGE', 'dogecoin')
ON DUPLICATE KEY UPDATE `coin_name` = VALUES(`coin_name`);
