package autotest.afe;

import autotest.common.StaticDataRepository;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Set;

/**
 * Utility methods.
 */
public class AfeUtils {
    public static final String PLATFORM_SUFFIX = " (platform)";
    
    public static final ClassFactory factory = new SiteClassFactory();
    
    public static String formatStatusCounts(JSONObject counts, String joinWith) {
        String result = "";
        Set<String> statusSet = counts.keySet();
        for (Iterator<String> i = statusSet.iterator(); i.hasNext();) {
            String status = i.next();
            int count = (int) counts.get(status).isNumber().doubleValue();
            result += Integer.toString(count) + " " + status;
            if (i.hasNext())
                result += joinWith;
        }
        return result;
    }
    
    public static String[] getLabelStrings() {
        return getFilteredLabelStrings(false, false);
    }
    
    protected static String[] getFilteredLabelStrings(boolean onlyPlatforms,
                                                      boolean onlyNonPlatforms) {
        assert( !(onlyPlatforms && onlyNonPlatforms));
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray labels = staticData.getData("labels").isArray();
        List<String> result = new ArrayList<String>();
        for (int i = 0; i < labels.size(); i++) {
            JSONObject label = labels.get(i).isObject();
            String name = label.get("name").isString().stringValue();
            boolean labelIsPlatform =
                label.get("platform").isNumber().doubleValue() != 0;
            if ((onlyPlatforms && labelIsPlatform) ||
                (onlyNonPlatforms && !labelIsPlatform)) {
                    result.add(name);
            } else if (!onlyPlatforms && !onlyNonPlatforms) {
                if (labelIsPlatform) {
                    name += PLATFORM_SUFFIX;
                }
                result.add(name);
            }
        }
        return result.toArray(new String[result.size()]);
    }
    
    public static String[] getPlatformStrings() {
      return getFilteredLabelStrings(true, false);
    }
    
    public static String[] getNonPlatformLabelStrings() {
        return getFilteredLabelStrings(false, true);
    }
    
    public static String decodeLabelName(String labelName) {
        if (labelName.endsWith(PLATFORM_SUFFIX)) {
            int nameLength = labelName.length() - PLATFORM_SUFFIX.length();
            return labelName.substring(0, nameLength);
        }
        return labelName;
    }
    
    public static JSONString getLockedText(JSONObject host) {
        boolean locked = host.get("locked").isNumber().doubleValue() > 0;
        return new JSONString(locked ? "Yes" : "No");
    }
}
