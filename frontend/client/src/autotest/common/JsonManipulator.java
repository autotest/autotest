package autotest.common;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class JsonManipulator {
    public static interface IFactory<T> {
        public T fromJsonObject(JSONObject object);
    }

    public static <T> List<T> createList(JSONArray objects, IFactory<T> factory) {
        List<T> list = new ArrayList<T>();
        for (JSONObject object : new JSONArrayList<JSONObject>(objects)) {
            list.add(factory.fromJsonObject(object));
        }
        return list;
    }
}
