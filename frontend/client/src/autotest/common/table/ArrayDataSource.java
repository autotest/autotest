package autotest.common.table;

import autotest.common.UnmodifiableSublistView;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.SortedSet;
import java.util.TreeSet;

/**
 * Data source that operates from a local array.  Does not support any 
 * filtering.
 */
public class ArrayDataSource<T extends JSONObject> implements DataSource {
    private class ArrayQuery extends DefaultQuery {
        public ArrayQuery() {
            super(null);
        }

        @Override
        public void getPage(Integer start, Integer maxCount, SortSpec[] sortOn,
                            DataCallback callback) {
            List<JSONObject> sortedData = new ArrayList<JSONObject>(data);
            if (sortOn != null) {
                Collections.sort(sortedData, new JSONObjectComparator(sortOn));
            }
            int startInt = start != null ? start.intValue() : 0;
            int maxCountInt = maxCount != null ? maxCount.intValue() : data.size();
            int size = Math.min(maxCountInt, data.size() - startInt);
            List<JSONObject> subList =
                new UnmodifiableSublistView<JSONObject>(sortedData, startInt, size);
            callback.handlePage(subList);
        }

        @Override
        public void getTotalResultCount(DataCallback callback) {
            callback.handleTotalResultCount(data.size());
        }
    }

    private SortedSet<T> data;
    private Query theQuery = new ArrayQuery(); // only need one for each instance

    /**
     * @param sortKeys keys that will be used to keep items sorted internally. We
     * do this to ensure we can find and remove items quickly.
     */
    public ArrayDataSource(String[] sortKeys) {
        SortSpec[] sortSpecs = new SortSpec[sortKeys.length];
        for (int i = 0; i < sortKeys.length; i++) {
            sortSpecs[i] = new SortSpec(sortKeys[i]);
        }
        data = new TreeSet<T>(new JSONObjectComparator(sortSpecs));
    }
    
    public void addItem(T item) {
        data.add(item);
    }
    
    public void removeItem(T item) {
        boolean wasPresent = data.remove(item);
        assert wasPresent;
    }
    
    public void clear() {
        data.clear();
    }
    
    public Collection<T> getItems() {
        return Collections.unmodifiableCollection(data);
    }

    @Override
    public void query(JSONObject params, DataCallback callback) {
        // ignore params since we don't support filtering
        callback.onQueryReady(theQuery);
    }
}
