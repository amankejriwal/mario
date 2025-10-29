-- Add comment column to user_events table for storing user feedback comments

ALTER TABLE user_events 
ADD COLUMN IF NOT EXISTS comment TEXT;

-- Add index for querying comments
CREATE INDEX IF NOT EXISTS idx_user_events_comment ON user_events(event_id) WHERE comment IS NOT NULL;

-- Verify the column was added
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'user_events' AND column_name = 'comment';
