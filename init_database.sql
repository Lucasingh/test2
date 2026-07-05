-- 跨学科前沿成果数据可视化面板 - 数据库初始化脚本
-- 升级后的新数据库结构

-- 创建数据库
CREATE DATABASE IF NOT EXISTS signals CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE signals;

-- 创建论文表（升级后的结构）
DROP TABLE IF EXISTS papers;

CREATE TABLE papers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(100) NOT NULL COMMENT '数据源类型',
    title VARCHAR(1024) NOT NULL COMMENT '标题',
    abstract TEXT COMMENT '摘要',
    url VARCHAR(512) COMMENT '原文链接',
    published_date DATE COMMENT '发布日期',
    crawled_date DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '采集时间',
    signal_type VARCHAR(50) DEFAULT 'paper' COMMENT '信号类型(paper/news)',
    theme_bucket VARCHAR(50) COMMENT '主题领域分类',
    field VARCHAR(255) COMMENT '具体学科领域',
    content_hash VARCHAR(64) UNIQUE COMMENT '内容哈希用于去重',
    is_starred BOOLEAN DEFAULT FALSE COMMENT '是否收藏',
    read_count INT DEFAULT 0 COMMENT '阅读次数',
    tags TEXT COMMENT '关键词标签(逗号分隔)',
    INDEX idx_source_type (source_type),
    INDEX idx_published_date (published_date),
    INDEX idx_theme_bucket (theme_bucket),
    INDEX idx_is_starred (is_starred),
    INDEX idx_content_hash (content_hash),
    FULLTEXT INDEX idx_fulltext (title, abstract)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建采集历史表
DROP TABLE IF EXISTS crawl_history;

CREATE TABLE crawl_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_type VARCHAR(100) NOT NULL COMMENT '数据源类型',
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    end_time DATETIME COMMENT '结束时间',
    papers_added INT DEFAULT 0 COMMENT '新增数量',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态',
    error_message TEXT COMMENT '错误信息',
    INDEX idx_source_type (source_type),
    INDEX idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建收藏表（可选，用于高级功能）
DROP TABLE IF EXISTS favorites;

CREATE TABLE favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    paper_id INT NOT NULL COMMENT '论文ID',
    note TEXT COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_paper_id (paper_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT '数据库初始化完成！' AS status;
