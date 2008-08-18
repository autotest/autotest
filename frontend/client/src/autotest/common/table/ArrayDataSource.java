package autotest.common.table;

import autotest.common.UnmodifiableSublistView;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;

/**
 * Data source that operates from a local array.  Does not support any 
 * filtering.
 */
public class ArrayDataSource<T extends JSONObject> implements DataSource {
    protected List<T> data = new ArrayList<T>();
    protected JSONObjectComparator comparator;
    
    /**
     * @param sortKeys keys that will be used to keep items sorted internally. We
     * do this to ensure we can find and remove items quickly.
     */
    public ArrayDataSource(String[] sortKeys) {
        SortSpec[] sortSpecs = new SortSpec[sortKeys.length];
        for (int i = 0; i < sortKeys.length; i++) {
            sortSpecs[i] = new SortSpec(sortKeys[i]);
        }
        comparator = new JSONObjectComparator(sortSpecs);
    }
    
    public void addItem(T item) {
        // insert in sorted order
        int insertPosition = Collections.binarySearch(data, item, comparator);
        if (insertPosition < 0)
            insertPosition = -insertPosition - 1; // see binarySearch() docs
        data.add(insertPosition, item);
    }
    
    public void removeItem(T item) {
        int position = Collections.binarySearch(data, item, comparator);
        assert position >= 0;
        data.remove(position);
    }
    
    public void clear() {
        data.clear();
    }
    
    public List<T> getItems() {
        return data;
    }
    
    protected JSONArray createJSONArray(Collection<T> objects) {
        JSONArray result = new JSONArray();
        int count = 0;
        for (T object : objects) {
            result.set(count, object);
            count++;
        }
        return result;
    }
    
    public void getPage(Integer start, Integer maxCount, SortSpec[] sortOn,
                        DataCallback callback) {
        List<T> sortedData = data;
        if (sortOn != null) {
            Collections.sort(sortedData, new JSONObjectComparator(sortOn));
        }
        int startInt = start != null ? start.intValue() : 0;
        int maxCountInt = maxCount != null ? maxCount.intValue() : data.size();
        int size = Math.min(maxCountInt, data.size() - startInt);
        List<T> subList =
            new UnmodifiableSublistView<T>(sortedData, startInt, size);
        callback.handlePage(createJSONArray(subList));
    }

    public void updateData(JSONObject params, DataCallback callback) {
        callback.onGotData(data.size());
    }

    public int getNumResults() {
        return data.size();
    }
}
