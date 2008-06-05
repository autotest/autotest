package autotest.afe;

import autotest.common.StaticDataRepository;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

import java.util.Iterator;
import java.util.Set;

/**
 * Utility methods.
 */
public class AfeUtils {
    public static final String PLATFORM_SUFFIX = " (platform)";
    
    public static final ClassFactory factory = new SiteClassFactory();
    
    public static String formatStatusCounts(JSONObject counts, String joinWith) {
        String result = "";
        Set statusSet = counts.keySet();
        for (Iterator i = statusSet.iterator(); i.hasNext();) {
            String status = (String) i.next();
            int count = (int) counts.get(status).isNumber().getValue();
            result += Integer.toString(count) + " " + status;
            if (i.hasNext())
                result += joinWith;
        }
        return result;
    }
    
    public static String[] getLabelStrings() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray labels = staticData.getData("labels").isArray();
        String[] result = new String[labels.size()];
        for (int i = 0; i < labels.size(); i++) {
            JSONObject label = labels.get(i).isObject();
            String name = label.get("name").isString().stringValue();
            boolean platform = label.get("platform").isNumber().getValue() != 0;
            if (platform) {
                name += PLATFORM_SUFFIX;
            }
            result[i] = name;
        }
        return result;
    }
    
    public static String decodeLabelName(String labelName) {
        if (labelName.endsWith(PLATFORM_SUFFIX)) {
            int nameLength = labelName.length() - PLATFORM_SUFFIX.length();
            return labelName.substring(0, nameLength);
        }
        return labelName;
    }
    
    public static JSONString getLockedText(JSONObject host) {
        boolean locked = host.get("locked").isNumber().getValue() > 0;
        return new JSONString(locked ? "Yes" : "No");
    }
}
