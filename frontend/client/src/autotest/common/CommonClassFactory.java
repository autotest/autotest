package autotest.common;

import com.google.gwt.user.client.ui.RootPanel;

public class CommonClassFactory {
    public static void globalInitialize() {
        setupMOTD();
    }
    
    public static void setupMOTD() {
        String motd = StaticDataRepository.getRepository().getData(
                "motd").isString().stringValue();
        RootPanel.get("motd").getElement().setInnerHTML(motd);
    }
}
