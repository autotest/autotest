package autotest.common.table;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

public interface DataSource {
    public static final int ASCENDING = 1, DESCENDING = -1;
    
    public interface DataCallback {
        public void onGotData(int totalCount);
        public void handlePage(JSONArray data);
    }
    
    public class DefaultDataCallback implements DataCallback {
        public void onGotData(int totalCount) {}
        public void handlePage(JSONArray data) {}
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
     * @param sortOn column name to sort on
     * @param sortDirection ASCENDING or DESCENDING
     */
    public void getPage(Integer start, Integer maxCount, 
                        String sortOn, Integer sortDirection,
                        final DataCallback callback);
    
    /**
     * Get the total number of results match the most recent updateData call.
     */
    public int getNumResults();
}
