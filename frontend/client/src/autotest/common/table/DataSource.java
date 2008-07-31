package autotest.common.table;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

public interface DataSource {
    public static enum SortDirection {ASCENDING, DESCENDING}
    
    public interface DataCallback {
        public void onGotData(int totalCount);
        public void handlePage(JSONArray data);
        public void onError(JSONObject errorObject);
    }
    
    public static class DefaultDataCallback implements DataCallback {
        public void onGotData(int totalCount) {}
        public void handlePage(JSONArray data) {}
        public void onError(JSONObject errorObject) {}
    }
    
    public static class SortSpec {
        private String field;
        private SortDirection direction;
        
        public SortSpec(String field, SortDirection direction) {
            this.field = field;
            this.direction = direction;
        }
        
        public SortSpec(String field) {
            this(field, SortDirection.ASCENDING);
        }
        
        public int getDirectionMultiplier() {
            return direction == SortDirection.ASCENDING ? 1 : -1;
        }

        public String getField() {
            return field;
        }

        public SortDirection getDirection() {
            return direction;
        }

        @Override
        public String toString() {
            String prefix = "";
            if (direction == SortDirection.DESCENDING) {
                prefix = "-";
            }
            return prefix + field;
        }
        
        public static SortSpec fromString(String sortString) {
            if (sortString.charAt(0) == '-') {
                return new SortSpec(sortString.substring(1), SortDirection.DESCENDING); 
            } else {
                return new SortSpec(sortString, SortDirection.ASCENDING);
            }
        }
    }
    
    /** 
     * Update the data source with the given filtering parameters.  After 
     * completion, callback.onGotData() will be called with the total number
     * of results maching the given parameters.
     * 
     */
    public void updateData(JSONObject params, final DataCallback callback);
    
    /**
     * Get a page of data.  After completion, callback.handlePage() will be 
     * called with the data.
     * @param start row to start with (for pagination)
     * @param maxCount maximum rows to be returned
     * @param sortOn list of columns + directions to sort on; results will be sorted by the first 
     *               field, then the second, etc.
     */
    public void getPage(Integer start, Integer maxCount, SortSpec[] sortOn, 
                        final DataCallback callback);
    
    /**
     * Get the total number of results match the most recent updateData call.
     */
    public int getNumResults();
}
