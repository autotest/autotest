package autotest.common;

import com.google.gwt.http.client.URL;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Utils {
    private static final String[][] escapeMappings = {
        {"&", "&amp;"},
        {">", "&gt;"},
        {"<", "&lt;"},
        {"\"", "&quot;"},
        {"'", "&apos;"},
    };

    /**
     * Converts a collection of Java <code>String</code>s into a <code>JSONArray
     * </code> of <code>JSONString</code>s.
     */
    public static JSONArray stringsToJSON(Collection<String> strings) {
        JSONArray result = new JSONArray();
        for(String s : strings) {
            result.set(result.size(), new JSONString(s));
        }
        return result;
    }

    /**
     * Converts a <code>JSONArray</code> of <code>JSONStrings</code> to an 
     * array of Java <code>Strings</code>.
     */
    public static String[] JSONtoStrings(JSONArray strings) {
        String[] result = new String[strings.size()];
        for (int i = 0; i < strings.size(); i++) {
            result[i] = strings.get(i).isString().stringValue();
        }
        return result;
    }

    /**
     * Converts a <code>JSONArray</code> of <code>JSONObjects</code> to an 
     * array of Java <code>Strings</code> by grabbing the specified field from
     * each object.
     */
    public static String[] JSONObjectsToStrings(JSONArray objects, String field) {
        String[] result = new String[objects.size()];
        for (int i = 0; i < objects.size(); i++) {
            JSONValue fieldValue = objects.get(i).isObject().get(field);
            result[i] = fieldValue.isString().stringValue();
        }
        return result;
    }

    /**
     * Get a value out of an array of size 1.
     * @return array[0]
     * @throws IllegalArgumentException if the array is not of size 1
     */
    public static JSONValue getSingleValueFromArray(JSONArray array) {
        if(array.size() != 1) {
            throw new IllegalArgumentException("Array is not of size 1");
        }
        return array.get(0);
    }

    public static JSONObject copyJSONObject(JSONObject source) {
        JSONObject dest = new JSONObject();
        for(String key : source.keySet()) {
            dest.put(key, source.get(key));
        }
        return dest;
    }
    
    public static String escape(String text) {
        for (String[] mapping : escapeMappings) {
            text = text.replaceAll(mapping[0], mapping[1]);
        }
        return text;
    }
    
    public static String unescape(String text) {
        // must iterate in reverse order
        for (int i = escapeMappings.length - 1; i >= 0; i--) {
            text = text.replaceAll(escapeMappings[i][1], escapeMappings[i][0]);
        }
        return text;
    }
    
    public static <T> List<T> wrapObjectWithList(T object) {
        List<T> list = new ArrayList<T>();
        list.add(object);
        return list;
    }
    
    public static <T> String joinStrings(String joiner, List<T> objects) {
        if (objects.size() == 0) {
            return "";
        }
        
        StringBuilder result = new StringBuilder(objects.get(0).toString());
        for (int i = 1; i < objects.size(); i++) {
            result.append(joiner);
            result.append(objects.get(i).toString());
        }
        return result.toString();
    }
    
    public static Map<String,String> decodeUrlArguments(String urlArguments) {
        Map<String, String> arguments = new HashMap<String, String>();
        String[] components = urlArguments.split("&");
        for (String component : components) {
            String[] parts = component.split("=");
            if (parts.length > 2) {
                throw new IllegalArgumentException();
            }
            String key = URL.decodeComponent(parts[0]);
            String value = "";
            if (parts.length == 2) {
                value = URL.decodeComponent(parts[1]);
            }
            arguments.put(key, value);
        }
        return arguments;
    }
    
    public static String encodeUrlArguments(Map<String, String> arguments) {
        List<String> components = new ArrayList<String>();
        for (Map.Entry<String, String> entry : arguments.entrySet()) {
            String key = URL.encodeComponent(entry.getKey());
            String value = URL.encodeComponent(entry.getValue());
            components.add(key + "=" + value);
        }
        return joinStrings("&", components);
    }

    /**
     * @param path should be of the form "123-showard/status.log" or just "123-showard"
     */
    public static String getLogsURL(String path) {
        String val = URL.encode("/results/" + path);
        return "/tko/retrieve_logs.cgi?job=" + val;
    }
}
