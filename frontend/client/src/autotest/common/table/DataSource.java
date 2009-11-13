package autotest.common.table;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.List;

public interface DataSource {
    public static enum SortDirection {ASCENDING, DESCENDING}

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

    public interface Query {
        public JSONObject getParams();

        /**
         * Get the total number of results matching this query.  After completion, 
         * callback.handleTotalResultCount() will be called with the count.
         */
        public void getTotalResultCount(final DataCallback callback);

        /**
         * Get a page of data.  After completion, callback.handlePage() will be 
         * called with the data.
         * @param start row to start with (for pagination)
         * @param maxCount maximum rows to be returned
         * @param sortOn list of columns + directions to sort on; results will be sorted by the
         *               first field, then the second, etc.
         */
        public void getPage(Integer start, Integer maxCount, SortSpec[] sortOn, 
                            final DataCallback callback);
    }

    abstract class DefaultQuery implements Query {
        protected JSONObject params;
        
        public DefaultQuery(JSONObject params) {
            if (params == null) {
                this.params = new JSONObject();
            } else {
                this.params = Utils.copyJSONObject(params);
            }
        }

        @Override
        public JSONObject getParams() {
            return Utils.copyJSONObject(params);
        }

        @Override
        public abstract void getPage(Integer start, Integer maxCount, SortSpec[] sortOn,
                                     DataCallback callback);

        @Override
        public abstract void getTotalResultCount(DataCallback callback);
    }

    public interface DataCallback {
        public void onQueryReady(Query query);
        public void handlePage(List<JSONObject> data);
        public void handleTotalResultCount(int totalCount);
        public void onError(JSONObject errorObject);
    }

    public static class DefaultDataCallback implements DataCallback {
        public void handlePage(List<JSONObject> data) {}
        public void handleTotalResultCount(int totalCount) {}
        public void onQueryReady(Query query) {}
        public void onError(JSONObject errorObject) {}
    }

    public void query(JSONObject params, final DataCallback callback);
}
