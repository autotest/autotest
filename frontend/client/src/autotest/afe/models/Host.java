package autotest.afe.models;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

public class Host extends JSONObject {
    public static Host fromJsonObject(JSONObject object) {
        assert object.containsKey("hostname");
        Host host = new Host();
        Utils.updateObject(host, object);
        return host;
    }

    @Override
    public boolean equals(Object other) {
        if (!(other instanceof Host)) {
            return false;
        }

        Host otherHost = (Host) other;
        return otherHost.getHostname().equals(getHostname());
    }

    @Override
    public int hashCode() {
        return getHostname().hashCode();
    }

    public String getHostname() {
        return Utils.jsonToString(get("hostname"));
    }
}
