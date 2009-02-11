package autotest.common;

import com.google.gwt.http.client.URL;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Utils {
    public static final String JSON_NULL = "<null>";
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
            result[i] = jsonToString(strings.get(i));
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
            result[i] = jsonToString(fieldValue);
        }
        return result;
    }
    
    public static JSONObject mapToJsonObject(Map<String, String> map) {
        JSONObject result = new JSONObject();
        for (Map.Entry<String, String> entry : map.entrySet()) {
            result.put(entry.getKey(), new JSONString(entry.getValue()));
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
            text = text.replace(mapping[0], mapping[1]);
        }
        return text;
    }
    
    public static String unescape(String text) {
        // must iterate in reverse order
        for (int i = escapeMappings.length - 1; i >= 0; i--) {
            text = text.replace(escapeMappings[i][1], escapeMappings[i][0]);
        }
        return text;
    }
    
    public static <T> List<T> wrapObjectWithList(T object) {
        List<T> list = new ArrayList<T>();
        list.add(object);
        return list;
    }
    
    public static <T> String joinStrings(String joiner, List<T> objects) {
        StringBuilder result = new StringBuilder();
        boolean first = true;
        for (T object : objects) {
            String piece = object.toString();
            if (piece.equals("")) {
                continue;
            }
            if (first) {
                first = false;
            } else {
                result.append(joiner);
            }
            result.append(piece);
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
            String key = decodeComponent(parts[0]);
            String value = "";
            if (parts.length == 2) {
                value = URL.decodeComponent(parts[1]);
            }
            arguments.put(key, value);
        }
        return arguments;
    }

    private static String decodeComponent(String component) {
        return URL.decodeComponent(component.replace("%27", "'"));
    }
    
    public static String encodeUrlArguments(Map<String, String> arguments) {
        List<String> components = new ArrayList<String>();
        for (Map.Entry<String, String> entry : arguments.entrySet()) {
            String key = encodeComponent(entry.getKey());
            String value = encodeComponent(entry.getValue());
            components.add(key + "=" + value);
        }
        return joinStrings("&", components);
    }

    private static String encodeComponent(String component) {
        return URL.encodeComponent(component).replace("'", "%27");
    }

    /**
     * @param path should be of the form "123-showard/status.log" or just "123-showard"
     */
    public static String getLogsURL(String path) {
        String val = URL.encode("/results/" + path);
        return "/tko/retrieve_logs.cgi?job=" + val;
    }
    
    public static String getJsonpLogsUrl(String path, String callbackName) {
        return getLogsURL(path) + "&jsonp_callback=" + callbackName;
    }

    public static String jsonToString(JSONValue value) {
        JSONString string;
        JSONNumber number;
        assert value != null;
        if ((string = value.isString()) != null) {
            return string.stringValue();
        }
        if ((number = value.isNumber()) != null) {
            return Integer.toString((int) number.doubleValue());
        }
        if (value.isNull() != null) {
            return JSON_NULL;
        }
        return value.toString();
    }

    public static String setDefaultValue(Map<String, String> map, String key, String defaultValue) {
        if (map.containsKey(key)) {
            return map.get(key);
        }
        map.put(key, defaultValue);
        return defaultValue;
    }
    
    public static JSONValue setDefaultValue(JSONObject object, String key, JSONValue defaultValue) {
        if (object.containsKey(key)) {
            return object.get(key);
        }
        object.put(key, defaultValue);
        return defaultValue;
    }
    
    public static List<String> splitList(String list, String splitRegex) {
        String[] parts = list.split(splitRegex);
        List<String> finalParts = new ArrayList<String>();
        for (String part : parts) {
            if (!part.equals("")) {
                finalParts.add(part);
            }
        }
        return finalParts;
    }
    
    public static List<String> splitList(String list) {
        return splitList(list, ",");
    }
    
    public static List<String> splitListWithSpaces(String list) {
        return splitList(list, "[,\\s]+");
    }

    public static void updateObject(JSONObject destination, JSONObject source) {
        if (source == null) {
            return;
        }
        for (String key : source.keySet()) {
            destination.put(key, source.get(key));
        }
    }
}
