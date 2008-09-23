package autotest.common.ui;

import com.google.gwt.dom.client.Element;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.Widget;

public class RealHyperlink extends Widget {
    private Element link;
    
    public RealHyperlink(String text) {
        link = DOM.createAnchor();
        link.setInnerText(text);
        setElement(link);
    }
    
    public void setOpensNewWindow(boolean opensNewWindow) {
        if (opensNewWindow) {
            link.setAttribute("target", "_blank");
        } else {
            link.removeAttribute("target");
        }
    }
    
    public void setHref(String href) {
        link.setAttribute("href", href);
    }
}
